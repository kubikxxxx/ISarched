# views.py
from django.db import transaction
from django.forms import modelformset_factory
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.template.defaultfilters import date
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.contrib.auth.forms import PasswordChangeForm
from django.http import HttpResponseForbidden, HttpResponse
from django.contrib.auth import update_session_auth_hash
from django.utils import timezone
from datetime import datetime, timedelta
from django.contrib import messages
from django.utils.timezone import now, localdate
from django.db.models import Sum
import re
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from django.db.models import Sum
from django.shortcuts import get_object_or_404, render
from django.utils.timezone import now
import holidays
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from simple_history.utils import update_change_reason
from simple_history.models import HistoricalRecords
from simple_history.utils import get_history_model_for_model
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import calendar
import datetime as dt
from decimal import Decimal
from .models import UredniZapis, RozsahText, UzaverkaMesice, PlanDen, OverheadRate
from .forms import LoginForm, ZakazkaForm, EmployeeForm, ClientForm, KlientPoznamkaForm, SubdodavkaForm, \
    SubdodavatelForm, UredniZapisForm, VykazForm, RozsahPraceFormSet, ZamestnanecZakazkaForm, CustomPasswordChangeForm, \
    EmployeeEditForm, RozsahPraceForm, RozsahPraceInlineForm, RozsahPraceEditFormSet, EmployeeWeeklyPlanForm, \
    OverheadRateForm
from .models import Zakazka, Zamestnanec, Klient, KlientPoznamka, Subdodavka, Subdodavatel, ZakazkaSubdodavka, \
    UredniZapis, ZakazkaZamestnanec, ZamestnanecZakazka, RozsahPrace


def _to_decimal(val: str | None, allow_empty: bool = False) -> Decimal | None:
    """
    Bezpečně převede '12 345,67' / '12345.67' -> Decimal.
    Vrátí None, pokud je hodnota prázdná nebo neplatná (pokud allow_empty=False).
    """
    if val is None:
        return Decimal("0") if allow_empty else None
    s = str(val).strip().replace(" ", "").replace("\u00A0", "").replace(",", ".")
    if s == "":
        return Decimal("0") if allow_empty else None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None

def login_view(request):
    if request.user.is_authenticated:
        return redirect('homepage')

    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.get_user())
        return redirect('homepage')

    return render(request, 'login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def homepage_view(request):
    aktivni = "1"

    if request.user.is_admin:
        aktivni = request.GET.get("aktivni", "1")
        zakazky = Zakazka.objects.all()
        if aktivni == "1":
            zakazky = zakazky.filter(zakazka_konec_skut__isnull=True)
    else:
        zakazky = Zakazka.objects.filter(
            prirazeni__zamestnanec=request.user,
            prirazeni__datum_prideleni__lte=now(),
            prirazeni__skryta=False
        )

    selected_zamestnanec_id = request.GET.get("detail_zamestnanec")
    zamestnanec_sidebar = Zamestnanec.objects.filter(
        id=selected_zamestnanec_id).first() if selected_zamestnanec_id else None
    selected_subdodavatel_id = request.GET.get("detail_subdodavatel")
    subdodavatel_sidebar = Subdodavatel.objects.filter(
        id=selected_subdodavatel_id).first() if selected_subdodavatel_id else None
    selected_subdodavka_id = request.GET.get("detail_subdodavka")
    subdodavka_sidebar = Subdodavka.objects.filter(
        id=selected_subdodavka_id).first() if selected_subdodavka_id else None
    selected_zamestnanci_id = request.GET.get("detail_zamestnanci")
    zakazka_zam = Zakazka.objects.filter(id=selected_zamestnanci_id).first() if selected_zamestnanci_id else None
    prirazeni = ZamestnanecZakazka.objects.filter(zakazka=zakazka_zam) if zakazka_zam else None
    zamestnanci_prirazeni = prirazeni.select_related('zamestnanec') if prirazeni else None
    prirazene_ids = zamestnanci_prirazeni.values_list('zamestnanec_id', flat=True) if zamestnanci_prirazeni else None
    zamestnanci = Zamestnanec.objects.all()
    klienti = Klient.objects.all()
    subdodavatele = Subdodavatel.objects.all()
    subdodavky = Subdodavka.objects.all()
    selected_zakazka_id = request.GET.get("detail_zakazka")
    zakazka_detail = Zakazka.objects.filter(id=selected_zakazka_id).first() if selected_zakazka_id else None
    selected_klient_id = request.GET.get("detail_klient")
    klient_detail = Klient.objects.filter(id=selected_klient_id).first() if selected_klient_id else None
    klient_poznamky = KlientPoznamka.objects.filter(klient_id=selected_klient_id).order_by(
        '-datum') if selected_klient_id else None
    uredni_zapisy = UredniZapis.objects.filter(zakazka=zakazka_detail) if zakazka_detail else None
    rozsahy_prace = RozsahPrace.objects.filter(zakazka=zakazka_detail) if zakazka_detail else None
    zamestnanec_filter_id = request.GET.get("vykazy_zamestnanec")
    vykazy = None

    if zakazka_detail:
        vykazy_qs = zakazka_detail.zakazkazamestnanec_set.all()
        if zamestnanec_filter_id:
            vykazy_qs = vykazy_qs.filter(zamestnanec_id=zamestnanec_filter_id)
        vykazy = vykazy_qs.select_related('zamestnanec').order_by('-den_prace')

    arched_subs_count = 0
    arched_subs_sum = 0
    if zakazka_detail:
        arched_subs = ZakazkaSubdodavka.objects.filter(
            zakazka=zakazka_detail,
            fakturuje_arched=True
        )
        arched_subs_count = arched_subs.count()
        arched_subs_sum = arched_subs.aggregate(Sum('cena'))['cena__sum'] or 0

    odpracovano_hodin = 0
    zbyva_hodin = 0
    barva_zbyva = "success"
    progress_percent = 0
    predpokladany_cas = 0

    # 🔢 výpočet hodin pro progress (admin = všichni; user = jen jeho)
    if zakazka_detail:
        vykazy_qs = zakazka_detail.zakazkazamestnanec_set.all()

        if request.user.is_admin:
            relevantni_vykazy = vykazy_qs
            predpokladany_cas = zakazka_detail.predpokladany_cas or 0
        else:
            relevantni_vykazy = vykazy_qs.filter(zamestnanec=request.user)
            predpokladany_cas = ZamestnanecZakazka.objects.filter(
                zakazka=zakazka_detail,
                zamestnanec=request.user
            ).aggregate(Sum('prideleno_hodin'))['prideleno_hodin__sum'] or 0

        for vykaz in relevantni_vykazy:
            if vykaz.cas_od and vykaz.cas_do:
                dt_od = datetime.combine(datetime.today(), vykaz.cas_od)
                dt_do = datetime.combine(datetime.today(), vykaz.cas_do)
                rozdil = dt_do - dt_od
                odpracovano_hodin += rozdil.total_seconds() / 3600

        zbyva_hodin = predpokladany_cas - odpracovano_hodin
        if predpokladany_cas > 0:
            podil = zbyva_hodin / predpokladany_cas
        else:
            podil = 1

        if podil <= 0:
            barva_zbyva = "danger"
        elif podil <= 0.1:
            barva_zbyva = "warning"
        else:
            barva_zbyva = "success"

        if predpokladany_cas > 0:
            progress_percent = min(100, round((odpracovano_hodin / predpokladany_cas) * 100, 1))

    # 💰 VÝNOSY PRO ADMINA: sazba zakázky × (odpracované hodiny NA ZAKÁZCE CELKEM) a × plán
    proj_rate = None
    rev_actual = None
    rev_plan = None
    if request.user.is_admin and zakazka_detail and getattr(zakazka_detail, "sazba_id", None):
        try:
            rate = Decimal(str(zakazka_detail.sazba.hodnota))
            # hodiny všech uživatelů na zakázce (ne podle filtru)
            hours_all = 0.0
            for v in zakazka_detail.zakazkazamestnanec_set.all():
                if v.cas_od and v.cas_do:
                    dt_od = datetime.combine(datetime.today(), v.cas_od)
                    dt_do = datetime.combine(datetime.today(), v.cas_do)
                    hours_all += max((dt_do - dt_od).total_seconds() / 3600, 0)

            proj_rate = rate
            rev_actual = (rate * Decimal(str(hours_all))).quantize(Decimal("0.01"))
            plan_hours = Decimal(str(zakazka_detail.predpokladany_cas or 0))
            rev_plan = (rate * plan_hours).quantize(Decimal("0.01"))
        except Exception:
            proj_rate = None
            rev_actual = None
            rev_plan = None

    historie_urednich_zaznamu = None
    historie_vykazu_prace = None
    if zakazka_detail:
        uredni_ids = UredniZapis.objects.filter(zakazka=zakazka_detail).values_list('id', flat=True)
        historie_urednich_zaznamu = get_history_model_for_model(UredniZapis).objects.filter(id__in=uredni_ids).order_by(
            '-history_date')
        vykaz_ids = ZakazkaZamestnanec.objects.filter(zakazka=zakazka_detail).values_list('id', flat=True)
        historie_vykazu_prace = get_history_model_for_model(ZakazkaZamestnanec).objects.filter(
            id__in=vykaz_ids).order_by('-history_date')

    prirazeni_vypocty = []
    if zamestnanci_prirazeni:
        for priraz in zamestnanci_prirazeni:
            prideleno = priraz.prideleno_hodin or 0
            odpracovano = 0
            vqs = ZakazkaZamestnanec.objects.filter(
                zakazka=zakazka_zam,
                zamestnanec=priraz.zamestnanec
            )
            for v in vqs:
                if v.cas_od and v.cas_do:
                    odpracovano += (
                        datetime.combine(datetime.today(), v.cas_do) -
                        datetime.combine(datetime.today(), v.cas_od)
                    ).total_seconds() / 3600
            zbyva = prideleno - odpracovano
            if prideleno > 0:
                podil = zbyva / prideleno
            else:
                podil = 1
            if podil <= 0:
                barva = "danger"
            elif podil <= 0.1:
                barva = "warning"
            else:
                barva = "success"

            vidi = priraz.datum_prideleni and priraz.datum_prideleni <= now() and not priraz.skryta
            datum_ok = priraz.datum_prideleni and priraz.datum_prideleni <= now()
            prirazeni_vypocty.append({
                'prirazeni': priraz,
                'prideleno': prideleno,
                'odpracovano': round(odpracovano, 1),
                'zbyva': round(zbyva, 1),
                'barva': barva,
                'skryta': priraz.skryta,
                'vidi': vidi,
                'datum_ok': datum_ok,
            })

    return render(request, 'homepage.html', {
        'zakazky': zakazky.order_by('zakazka_cislo'),
        'is_admin': request.user.is_admin,
        'zamestnanci': zamestnanci,
        'klienti': klienti,
        'zakazka_detail': zakazka_detail,
        'klient_detail': klient_detail,
        'klient_poznamky': klient_poznamky,
        'uredni_zapisy': uredni_zapisy,
        'subdodavatele': subdodavatele,
        'subdodavky': subdodavky,
        'aktivni': aktivni,
        'selected_zamestnanci_id': selected_zamestnanci_id,
        'zamestnanci_prirazeni': zamestnanci_prirazeni,
        'zakazka_zam': zakazka_zam,
        'prirazene_ids': prirazene_ids,
        'prirazeni': prirazeni,
        'zamestnanec_sidebar': zamestnanec_sidebar,
        'subdodavatel_sidebar': subdodavatel_sidebar,
        'subdodavka_sidebar': subdodavka_sidebar,
        'rozsahy_prace': rozsahy_prace,
        'arched_subs_count': arched_subs_count,
        'arched_subs_sum': arched_subs_sum,
        'vykazy': vykazy,
        'zamestnanci_v_zakazce': ZakazkaZamestnanec.objects.filter(zakazka=zakazka_detail).values_list(
            'zamestnanec__id', 'zamestnanec__jmeno', 'zamestnanec__prijmeni').distinct(),
        'vykazy_zamestnanec': zamestnanec_filter_id,
        'odpracovano_hodin': odpracovano_hodin,
        'zbyva_hodin': zbyva_hodin,
        'barva_zbyva': barva_zbyva,
        'progress_percent': progress_percent,
        'predpokladany_cas': predpokladany_cas,
        'historie_urednich_zaznamu': historie_urednich_zaznamu,
        'historie_vykazu_prace': historie_vykazu_prace,
        'prirazeni_vypocty': prirazeni_vypocty,
        'proj_rate': proj_rate,
        'rev_actual': rev_actual,
        'rev_plan': rev_plan,
    })



@login_required
def create_zakazka_view(request):
    if not request.user.is_admin:
        return HttpResponseForbidden("Pouze administrátor může vytvářet zakázky.")

    if request.method == 'POST':
        form = ZakazkaForm(request.POST)
        formset = RozsahPraceFormSet(request.POST, queryset=RozsahPrace.objects.none())

        if form.is_valid() and formset.is_valid():
            zakazka = form.save()

            for subform in formset:
                if subform.cleaned_data and not subform.cleaned_data.get('DELETE', False):
                    novy_text = subform.cleaned_data.get('novy_text')
                    existujici_text = subform.cleaned_data.get('text')

                    if novy_text:
                        rozsah_text = RozsahText.objects.create(text=novy_text)
                    elif existujici_text:
                        rozsah_text = existujici_text
                    else:
                        continue  # ani jedno není vyplněno → přeskoč

                    rozsah = RozsahPrace(
                        zakazka=zakazka,
                        text=rozsah_text,
                        vytvoril=request.user
                    )
                    rozsah.save()

            return redirect('homepage')
        else:
            print("Form errors:", form.errors)
            print("Formset errors:", formset.errors)

    else:
        form = ZakazkaForm()
        formset = RozsahPraceFormSet(queryset=RozsahPrace.objects.none())

    return render(request, 'zakazka_form.html', {
        'form': form,
        'formset': formset,
        'is_edit': False
    })



@login_required
def edit_zakazka_view(request, zakazka_id):
    if not request.user.is_admin:
        return HttpResponseForbidden("Pouze administrátor může upravovat zakázky.")

    zakazka = get_object_or_404(Zakazka, id=zakazka_id)

    if request.method == 'POST':
        form = ZakazkaForm(request.POST, instance=zakazka)

        if form.is_valid():
            form.save()
            return redirect(f'/homepage/?detail_zakazka={zakazka_id}')
        else:
            print("Form errors:", form.errors)
    else:
        form = ZakazkaForm(instance=zakazka)

    return render(request, 'zakazka_form.html', {
        'form': form,
        'is_edit': 'True',
        'zakazka': zakazka,
    })



@login_required
def delete_zakazka_view(request, zakazka_id):
    if not request.user.is_admin:
        return HttpResponseForbidden("Pouze administrátor může mazat zakázky.")

    zakazka = get_object_or_404(Zakazka, id=zakazka_id)
    if request.method == 'POST':
        zakazka.delete()
        return redirect('homepage')

    return render(request, 'zakazka_confirm_delete.html', {'zakazka': zakazka})


@login_required
def zakazka_subdodavky_view(request, zakazka_id):
    zakazka = get_object_or_404(Zakazka, id=zakazka_id)
    subdodavky = Subdodavka.objects.all()
    subdodavatele = Subdodavatel.objects.all()
    assigned = ZakazkaSubdodavka.objects.filter(zakazka=zakazka)

    if request.method == "POST":
        ZakazkaSubdodavka.objects.filter(zakazka=zakazka).delete()

        selected_ids = request.POST.getlist("subdodavka")
        for sid in selected_ids:
            sub_id = int(sid)
            subdodavatel_id = request.POST.get(f"subdodavatel_{sub_id}")
            cena_raw = request.POST.get(f"cena_{sub_id}")
            navyseni_raw = request.POST.get(f"navyseni_{sub_id}")
            fakturace = request.POST.get(f"fakturace_{sub_id}")  # "klient" | "arched"

            cena = _to_decimal(cena_raw)
            navyseni = _to_decimal(navyseni_raw)

            # Validace vstupů
            if not subdodavatel_id or cena is None or navyseni is None or fakturace not in ("klient", "arched"):
                messages.error(
                    request,
                    f"Chyba u subdodávky ID {sub_id}: vyplňte subdodavatele, cenu a navýšení (číslo)."
                )
                return redirect(request.path)

            # (volitelné) zaokrouhlení na 2 desetinná místa
            cena = cena.quantize(Decimal("0.01"))
            navyseni = navyseni.quantize(Decimal("0.01"))

            ZakazkaSubdodavka.objects.create(
                zakazka=zakazka,
                subdodavka_id=sub_id,
                subdodavatel_id=int(subdodavatel_id),
                cena=cena,
                navyseni=navyseni,
                fakturuje_klientovi=(fakturace == "klient"),
                fakturuje_arched=(fakturace == "arched"),
            )

        messages.success(request, "Subdodávky byly uloženy.")
        return redirect("homepage")

    return render(request, "zakazka_subdodavky_form.html", {
        "zakazka": zakazka,
        "subdodavky": subdodavky,
        "subdodavatele": subdodavatele,
        "assigned": assigned,
    })


@login_required
def employee_create_view(request):
    if not request.user.is_admin:
        return HttpResponseForbidden("Pouze admin může přidávat zaměstnance.")

    if request.method == 'POST':
        form = EmployeeForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.jmeno = form.cleaned_data['jmeno']
            user.prijmeni = form.cleaned_data['prijmeni']
            user.is_admin = form.cleaned_data['is_admin']
            user.save()
            return redirect('homepage')
    else:
        form = EmployeeForm()

    return render(request, 'employee_form.html', {'form': form})


@login_required
def client_create_view(request):
    if request.method == 'POST':
        form = ClientForm(request.POST)
        if 'nacist_z_ares' in request.POST:
            ico = request.POST.get('ico')
            data = nacti_ares(ico)
            if data:
                form = ClientForm(initial=data)
        elif 'overit_dph' in request.POST:
            dic = request.POST.get('dic')
            spolehlivy = over_dph_spolehlivost(dic)
            return render(request, 'client_form.html', {'form': form, 'spolehlivy': spolehlivy})
        elif form.is_valid():
            form.save()
            return redirect('homepage')
    else:
        form = ClientForm()

    return render(request, 'client_form.html', {'form': form})


@login_required
def client_note_create_view(request, klient_id):
    if not request.user.is_admin:
        return HttpResponseForbidden("Pouze admin může přidávat poznámky.")

    klient = get_object_or_404(Klient, id=klient_id)

    if request.method == 'POST':
        form = KlientPoznamkaForm(request.POST)
        if form.is_valid():
            note = form.save(commit=False)
            note.klient = klient
            note.datum = timezone.now()
            note.save()
            return redirect(f'/homepage/?detail_klient={klient_id}')
    else:
        form = KlientPoznamkaForm()

    return render(request, 'client_poznamka_form.html', {'form': form, 'klient': klient})


@login_required
def client_edit_view(request, klient_id):
    if not request.user.is_admin:
        return HttpResponseForbidden("Pouze admin může upravovat klienty.")

    klient = get_object_or_404(Klient, id=klient_id)

    if request.method == 'POST':
        form = ClientForm(request.POST, instance=klient)
        if form.is_valid():
            form.save()
            return redirect(f'/homepage/?detail_klient={klient_id}')
    else:
        form = ClientForm(instance=klient)

    return render(request, 'client_form.html', {'form': form})


@login_required
def create_subdodavka_view(request):
    if not request.user.is_admin:
        return HttpResponseForbidden("Pouze admin může přidávat subdodávky.")

    if request.method == 'POST':
        form = SubdodavkaForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('homepage')
    else:
        form = SubdodavkaForm()

    return render(request, 'subdodavka_form.html', {'form': form})


@login_required
def edit_subdodavka_view(request, subdodavka_id):
    if not request.user.is_admin:
        return HttpResponseForbidden("Pouze admin může upravovat subdodávky.")

    subdodavka = get_object_or_404(Subdodavka, id=subdodavka_id)

    if request.method == 'POST':
        form = SubdodavkaForm(request.POST, instance=subdodavka)
        if form.is_valid():
            form.save()
            return redirect(f'/homepage/?detail_subdodavka={subdodavka_id}')
    else:
        form = SubdodavkaForm(instance=subdodavka)

    return render(request, 'subdodavka_form.html', {'form': form, 'is_edit': True})


@login_required
def create_subdodavatel_view(request):
    if not request.user.is_admin:
        return HttpResponseForbidden("Pouze admin může přidávat subdodavatele.")

    if request.method == 'POST':
        form = SubdodavatelForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('homepage')
    else:
        form = SubdodavatelForm()

    return render(request, 'subdodavatel_form.html', {'form': form})


@login_required
def uredni_zapis_create_view(request, zakazka_id):
    zakazka = get_object_or_404(Zakazka, id=zakazka_id)
    if request.method == 'POST':
        form = UredniZapisForm(request.POST)
        if form.is_valid():
            zapis = form.save(commit=False)
            zapis.zakazka = zakazka
            zapis.vytvoril = request.user
            zapis.splneno = form.cleaned_data.get('splneno', False)
            zapis.save()
            return redirect(f'/homepage/?detail_zakazka={zakazka_id}')
    else:
        form = UredniZapisForm()
    return render(request, 'uredni_zapis_form.html', {'form': form, 'zakazka': zakazka})


@login_required
def uredni_zapis_edit_view(request, zapis_id):
    zapis = get_object_or_404(UredniZapis, id=zapis_id)
    if request.method == 'POST':
        form = UredniZapisForm(request.POST, instance=zapis)
        if form.is_valid():
            form.save()
            return redirect(f'/homepage/?detail_zakazka={zapis.zakazka.id}')
    else:
        form = UredniZapisForm(instance=zapis)
    return render(request, 'uredni_zapis_form.html', {'form': form, 'zakazka': zapis.zakazka})


def prirazeni_view(request, zakazka_id):
    zakazka = get_object_or_404(Zakazka, id=zakazka_id)

    if request.method == 'POST':
        form = ZamestnanecZakazkaForm(request.POST)
        if form.is_valid():
            prirazeni = form.save(commit=False)
            prirazeni.zakazka = zakazka
            prirazeni.save()
            return redirect(f'/homepage/?detail_zamestnanci={zakazka.id}')
    else:
        form = ZamestnanecZakazkaForm()

    return render(request, 'prirazeni_form.html', {
        'prirazeni_form': form,
        'zakazka_id': zakazka.id
    })


def upravit_prirazeni_view(request, prirazeni_id):
    prirazeni = get_object_or_404(ZamestnanecZakazka, id=prirazeni_id)
    zakazka_id = prirazeni.zakazka.id

    if request.method == 'POST':
        form = ZamestnanecZakazkaForm(request.POST, instance=prirazeni)
        if form.is_valid():
            form.save()
            return redirect(f'/homepage/?detail_zamestnanci={zakazka_id}')
    else:
        form = ZamestnanecZakazkaForm(instance=prirazeni)

    return render(request, 'upravit_prirazeni_form.html', {
        'form': form,
        'zakazka_id': zakazka_id,
        'prirazeni': prirazeni,
    })


@login_required
def vykaz_create_view(request, zakazka_id):
    zakazka = get_object_or_404(Zakazka, id=zakazka_id)

    if request.method == "POST":
        den_prace_str = request.POST.get("den_prace")
        if den_prace_str:
            den_prace = date.fromisoformat(den_prace_str)
        else:
            den_prace = date.today()

        # kontrola uzavření měsíce
        if UzaverkaMesice.objects.filter(
            zamestnanec=request.user,
            rok=den_prace.year,
            mesic=den_prace.month
        ).exists():
            return render(request, 'alert_redirect.html', {
                'alert_text': "Tento měsíc je již uzavřen – nový výkaz nelze vytvořit.",
                'redirect_url': reverse("homepage")
            })

    # kontrola oprávnění
    if not request.user.is_admin and not ZamestnanecZakazka.objects.filter(
        zakazka=zakazka,
        zamestnanec=request.user
    ).exists():
        return HttpResponseForbidden("Nemáte oprávnění přidávat výkazy k této zakázce.")

    if request.method == 'POST':
        form = VykazForm(request.POST)
        if form.is_valid():
            vykaz = form.save(commit=False)
            vykaz.zakazka = zakazka
            vykaz.zamestnanec = request.user
            vykaz.save()
            return redirect(f'/homepage/?detail_zakazka={zakazka_id}')
    else:
        form = VykazForm(initial={'den_prace': now().date()})

    return render(request, 'vykaz_form.html', {
        'form': form,
        'zakazka': zakazka,
    })


@login_required
def ukoncit_zakazku_view(request, zakazka_id):
    if request.user.is_admin:
        zakazka = get_object_or_404(Zakazka, pk=zakazka_id)
        zakazka.zakazka_konec_skut = now()
        zakazka.save()
    return redirect('/homepage/?detail_zakazka=' + str(zakazka_id))


@require_POST
@login_required
def toggle_rozsah_splneno(request, pk):
    rozsah = get_object_or_404(RozsahPrace, pk=pk)
    rozsah.splneno = not rozsah.splneno
    rozsah.save()
    return redirect(request.META.get('HTTP_REFERER', '/'))


@login_required
def change_password_view(request, zamestnanec_id):
    zamestnanec = get_object_or_404(Zamestnanec, id=zamestnanec_id)

    if request.method == 'POST':
        form = CustomPasswordChangeForm(zamestnanec, request.POST)
        if form.is_valid():
            form.save()
            return redirect('homepage')
    else:
        form = CustomPasswordChangeForm(zamestnanec)

    return render(request, 'change_password.html', {
        'form': form,
        'zamestnanec': zamestnanec
    })


@require_POST
@csrf_exempt
def nacti_ares(request):
    ico = request.POST.get("ico")
    if not ico:
        return JsonResponse({"error": "IČO není zadáno"}, status=400)

    url = f"https://wwwinfo.mfcr.cz/cgi-bin/ares/darv_bas.cgi?ico={ico}"
    try:
        r = requests.get(url)
        if r.status_code != 200:
            return JsonResponse({"error": "Chyba při dotazu na ARES"}, status=500)

        from xml.etree import ElementTree as ET
        root = ET.fromstring(r.content)
        ns = {'are': 'http://wwwinfo.mfcr.cz/ares/xml_doc/schemas/ares/ares_answer/v_1.0.3'}

        zaznam = root.find('.//are:ZAU', ns)
        if zaznam is None:
            return JsonResponse({"error": "Záznam nebyl nalezen"}, status=404)

        nazev = zaznam.findtext('are:OF', default='', namespaces=ns)
        dic = zaznam.findtext('are:DIC', default='', namespaces=ns)
        ulice = zaznam.findtext('are:AD/are:NU', default='', namespaces=ns)
        obec = zaznam.findtext('are:AD/are:N', default='', namespaces=ns)
        psc = zaznam.findtext('are:AD/are:PSC', default='', namespaces=ns)

        return JsonResponse({
            "nazev": nazev,
            "dic": dic,
            "ulice": ulice,
            "obec": obec,
            "psc": psc
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@require_POST
@csrf_exempt
def over_dph_spolehlivost(request):
    dic = request.POST.get("dic")
    if not dic:
        return JsonResponse({"error": "DIČ není zadáno"}, status=400)

    url = f"https://adisreg.mfcr.cz/adistc/adis/idpr_pub/dpr_info.jsp?dic={dic}&obdobi=2025"
    try:
        r = requests.get(url, timeout=5)
        obsah = r.text
        spolehlivy = "je spolehlivým plátcem" in obsah.lower()
        return JsonResponse({"spolehlivy": spolehlivy})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def edit_subdodavatel_view(request, subdodavatel_id):
    subdodavatel = get_object_or_404(Subdodavatel, id=subdodavatel_id)
    if request.method == 'POST':
        form = SubdodavatelForm(request.POST, instance=subdodavatel)
        if form.is_valid():
            form.save()
            messages.success(request, "Subdodavatel byl úspěšně upraven.")
            return redirect('homepage')  # nebo redirect zpět na detail zakázky
    else:
        form = SubdodavatelForm(instance=subdodavatel)

    return render(request, 'subdodavatel_form.html', {'form': form, 'subdodavatel': subdodavatel})


@login_required
def edit_employee_view(request, zamestnanec_id):
    zamestnanec = get_object_or_404(Zamestnanec, id=zamestnanec_id)
    if request.method == 'POST':
        form = EmployeeEditForm(request.POST, instance=zamestnanec)
        if form.is_valid():
            form.save()
            messages.success(request, "Zaměstnanec byl úspěšně upraven.")
            return redirect('homepage')
    else:
        form = EmployeeEditForm(instance=zamestnanec)

    return render(request, 'employee_form.html', {'form': form, 'zamestnanec': zamestnanec})

@require_POST
@login_required
def toggle_viditelnost_view(request, prirazeni_id):
    prirazeni = get_object_or_404(ZamestnanecZakazka, id=prirazeni_id)

    # Změna viditelnosti pouze pokud má být viditelný (datum přidělení ≤ dnes)
    if prirazeni.datum_prideleni and prirazeni.datum_prideleni <= now():
        prirazeni.skryta = not prirazeni.skryta
        prirazeni.save()

    return redirect(f'/homepage/?detail_zamestnanci={prirazeni.zakazka.id}')






@login_required
def vykaz_edit_view(request, vykaz_id):
    vykaz = get_object_or_404(ZakazkaZamestnanec, id=vykaz_id)

    # oprávnění
    if not request.user.is_admin and request.user != vykaz.zamestnanec:
        return HttpResponseForbidden("Nemáte oprávnění upravovat tento výkaz.")

    # zákaz editace uzavřeného původního měsíce
    if UzaverkaMesice.objects.filter(
        zamestnanec=vykaz.zamestnanec,
        rok=vykaz.den_prace.year,
        mesic=vykaz.den_prace.month
    ).exists():
        return render(request, 'alert_redirect.html', {
            'alert_text': "Tento měsíc je již uzavřen – výkaz nelze upravit.",
            'redirect_url': reverse("homepage") + f"?detail_zakazka={vykaz.zakazka.id}"
        })

    if request.method == 'POST':
        form = VykazForm(request.POST, instance=vykaz)
        if form.is_valid():
            new_den = form.cleaned_data.get('den_prace') or vykaz.den_prace
            if UzaverkaMesice.objects.filter(
                zamestnanec=vykaz.zamestnanec,
                rok=new_den.year,
                mesic=new_den.month
            ).exists():
                return render(request, 'alert_redirect.html', {
                    'alert_text': "Cílový měsíc je uzavřen – změnu nelze uložit.",
                    'redirect_url': reverse("homepage") + f"?detail_zakazka={vykaz.zakazka.id}"
                })

            form.save()
            return redirect(f'/homepage/?detail_zakazka={vykaz.zakazka.id}')
    else:
        form = VykazForm(instance=vykaz)

    return render(request, 'vykaz_edit.html', {
        'form': form,
        'vykaz': vykaz,
        'zakazka_id': vykaz.zakazka.id,
    })

@login_required
def historie_zapisu_view(request, zapis_id):
    zapis = get_object_or_404(UredniZapis, id=zapis_id)
    HistoryModel = get_history_model_for_model(UredniZapis)
    historie_qs = HistoryModel.objects.filter(id=zapis_id).order_by('-history_date')
    historie = list(historie_qs)  # <== převod na list
    model_fields = [f for f in UredniZapis._meta.get_fields() if f.concrete and not f.many_to_many and not f.auto_created]

    return render(request, 'zapis_historie.html', {
        'zapis': zapis,
        'historie': historie,
        'model_fields': model_fields,
    })

@login_required
def vykaz_history_view(request, vykaz_id):
    vykaz = get_object_or_404(ZakazkaZamestnanec, id=vykaz_id)
    HistoryModel = get_history_model_for_model(ZakazkaZamestnanec)
    historie_qs = HistoryModel.objects.filter(id=vykaz_id).order_by('history_date')

    historie = []
    for i, h in enumerate(historie_qs):
        previous = historie_qs[i - 1] if i > 0 else None
        historie.append({
            'current': h,
            'previous': previous
        })

    model_fields = [
        f for f in ZakazkaZamestnanec._meta.get_fields()
        if f.concrete and not f.many_to_many and not f.auto_created
    ]

    return render(request, 'vykaz_history.html', {
        'vykaz': vykaz,
        'historie': historie,
        'model_fields': model_fields,
    })

@login_required
def zakazka_rozsahy_view(request, zakazka_id):
    zakazka = get_object_or_404(Zakazka, pk=zakazka_id)

    if request.method == "POST":
        formset = RozsahPraceEditFormSet(request.POST, queryset=RozsahPrace.objects.filter(zakazka=zakazka))
        if formset.is_valid():
            for form in formset:
                if form.cleaned_data.get('DELETE'):
                    if form.instance.pk:
                        form.instance.delete()
                    continue

                text_value = form.cleaned_data.get('text_value', '').strip()
                if not text_value:
                    continue

                rt, _ = RozsahText.objects.get_or_create(text=text_value)

                if form.instance.pk:  # úprava existujícího
                    form.instance.text = rt
                    form.instance.save()
                else:  # nový řádek
                    RozsahPrace.objects.create(
                        zakazka=zakazka,
                        text=rt,
                        vytvoril=request.user
                    )

            messages.success(request, "Rozsahy práce byly úspěšně upraveny.")
            return redirect(f"{reverse('homepage')}?detail_zakazka={zakazka.id}")
    else:
        formset = RozsahPraceEditFormSet(queryset=RozsahPrace.objects.filter(zakazka=zakazka))

    return render(request, 'zakazka_rozsahy.html', {
        'zakazka': zakazka,
        'formset': formset
    })

def _easter_sunday(year: int) -> dt.date:
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return dt.date(year, month, day)

def _cz_holidays(year: int) -> set[dt.date]:
    easter_mon = _easter_sunday(year) + dt.timedelta(days=1)
    fixed = {
        (1,1),(5,1),(5,8),(7,5),(7,6),(9,28),(10,28),(11,17),(12,24),(12,25),(12,26)
    }
    s = {dt.date(year, m, d) for (m, d) in fixed}
    s.add(easter_mon)
    return s

def _month_bounds(year: int, month: int) -> tuple[dt.date, dt.date, int]:
    first = dt.date(year, month, 1)
    _, ndays = calendar.monthrange(year, month)
    last = dt.date(year, month, ndays)
    return first, last, ndays

def _hours_between(date_: dt.date, t_from: dt.time | None, t_to: dt.time | None) -> float:
    if not (t_from and t_to):
        return 0.0
    start = dt.datetime.combine(date_, t_from)
    end = dt.datetime.combine(date_, t_to)
    delta = end - start
    return max(delta.total_seconds() / 3600.0, 0.0)

def _month_nav(year: int, month: int) -> tuple[tuple[int,int], tuple[int,int]]:
    prev_y = year - 1 if month == 1 else year
    prev_m = 12 if month == 1 else month - 1
    next_y = year + 1 if month == 12 else year
    next_m = 1 if month == 12 else month + 1
    return (prev_y, prev_m), (next_y, next_m)

def _month_label(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"

def _plan_for_day(d: dt.date, holidays: set[dt.date]) -> int:
    return 0 if (d.weekday() >= 5 or d in holidays) else 8


@login_required
def zamestnanec_timesheet_view(request, zamestnanec_id):
    """
    Timesheet zaměstnance (měsíc × zakázky) + NOVĚ:
      - poslední sloupec „Km“ = součet naj. km pro danou zakázku v daném měsíci
      - dole zobrazen celkový součet km za měsíc
    """
    from decimal import Decimal
    import datetime as dt
    import calendar

    zam = get_object_or_404(Zamestnanec, pk=zamestnanec_id)

    # vybraný měsíc (ym=YYYY-MM) nebo aktuální
    ym = request.GET.get("ym")
    if ym:
        year, month = map(int, ym.split("-"))
    else:
        today = now().date()
        year, month = today.year, today.month

    ndays = calendar.monthrange(year, month)[1]
    first_day = dt.date(year, month, 1)
    last_day = dt.date(year, month, ndays)

    # pro šipky
    (prev_y, prev_m), (next_y, next_m) = _month_nav(year, month)
    prev_ym = _month_label(prev_y, prev_m)
    next_ym = _month_label(next_y, next_m)

    holidays = _cz_holidays(year)

    # výkazy v měsíci
    qs = (
        ZakazkaZamestnanec.objects
        .filter(zamestnanec=zam, den_prace__gte=first_day, den_prace__lte=last_day)
        .select_related("zakazka")
        .order_by("zakazka__zakazka_cislo", "den_prace")
    )

    # stabilní pořadí zakázek
    zakazky_order = []
    seen = set()
    for v in qs:
        if v.zakazka_id not in seen:
            zakazky_order.append(v.zakazka)
            seen.add(v.zakazka_id)

    # mřížka hodin + km po zakázkách
    grid = {z.id: [Decimal("0.0")] * ndays for z in zakazky_order}
    km_by_z = {z.id: Decimal("0.0") for z in zakazky_order}

    for v in qs:
        idx = (v.den_prace - first_day).days
        hrs = Decimal(str(_hours_between(v.den_prace, v.cas_od, v.cas_do)))
        grid.setdefault(v.zakazka_id, [Decimal("0.0")] * ndays)
        grid[v.zakazka_id][idx] += hrs

        km = Decimal(str(v.najete_km or 0))
        km_by_z[v.zakazka_id] = km_by_z.get(v.zakazka_id, Decimal("0.0")) + km

    # denní příznaky, plán a součty
    sum_by_day = [Decimal("0.0")] * ndays
    days_meta = []
    plan_by_day = []
    for i in range(ndays):
        dte = first_day + dt.timedelta(days=i)
        weekend = dte.weekday() >= 5
        holiday = dte in holidays
        # plán z weekly plánu zaměstnance + svátky (pokud weekly plán používáš, jinak 8/0)
        plan_i = _plan_for_day(dte, holidays)  # nebo tvůj vlastní výpočet z weekly plánu
        plan_by_day.append(plan_i)

        total_d = Decimal("0.0")
        for zvals in grid.values():
            total_d += zvals[i]
        sum_by_day[i] = total_d

        diff_i = total_d - Decimal(str(plan_i))

        days_meta.append({
            "date": dte,
            "num": i + 1,
            "weekend": weekend,
            "holiday": holiday,
            "plan": plan_i,
            "sum": total_d,
            "diff": diff_i,
            "diff_pos": diff_i > 0,
            "diff_neg": diff_i < 0,
        })

    # řádky tabulky
    rows = []
    month_total = Decimal("0.0")
    month_km_total = Decimal("0.0")

    for z in zakazky_order:
        vals = [v for v in grid.get(z.id, [Decimal("0.0")] * ndays)]
        row_total = sum(vals, Decimal("0.0"))
        km_total = km_by_z.get(z.id, Decimal("0.0"))

        cells = [{
            "value": vals[i],
            "weekend": days_meta[i]["weekend"],
            "holiday": days_meta[i]["holiday"],
        } for i in range(ndays)]

        rows.append({
            "zakazka": z,
            "cells": cells,
            "total": row_total,
            "km_total": km_total,
        })
        month_total += row_total
        month_km_total += km_total

    plan_total = sum((Decimal(str(p)) for p in plan_by_day), Decimal("0.0"))
    diff_total = (month_total - plan_total)

    # banka hodin
    bank_now = getattr(zam, "banka_hodin", None)
    if bank_now is None:
        bank_now = UzaverkaMesice.objects.filter(zamestnanec=zam).aggregate(s=Sum("delta_hodin"))["s"] or Decimal("0.0")
    else:
        bank_now = Decimal(str(bank_now))

    closed_rec = UzaverkaMesice.objects.filter(zamestnanec=zam, rok=year, mesic=month).first()
    month_closed = bool(closed_rec)
    projected_bank = bank_now if month_closed else (bank_now + diff_total)

    context = {
        "zamestnanec": zam,
        "year": year,
        "month": month,
        "ym": f"{year:04d}-{month:02d}",
        "first_day": first_day,
        "last_day": last_day,
        "prev_ym": prev_ym,
        "next_ym": next_ym,

        "days": days_meta,
        "rows": rows,
        "plan_total": plan_total,
        "month_total": month_total,
        "diff_total": diff_total,

        "month_km_total": month_km_total,

        "bank_now": bank_now,
        "projected_bank": projected_bank,
        "month_closed": month_closed,
    }
    return render(request, "zamestnanec_timesheet.html", context)


@login_required
def uzavrit_mesic_view(request, zamestnanec_id: int, rok: int, mesic: int):
    """
    Uzavře měsíc (GET pro jednoduchost – interní nástroj). Spočítá rozdíl a připíše do banky hodin.
    """
    zam = get_object_or_404(Zamestnanec, pk=zamestnanec_id)
    rok = int(rok); mesic = int(mesic)

    if UzaverkaMesice.objects.filter(zamestnanec=zam, rok=rok, mesic=mesic).exists():
        messages.info(request, "Tento měsíc je už uzavřen.")
        return redirect(f"{reverse('zamestnanec_timesheet', args=[zam.id])}?ym={_month_label(rok, mesic)}")

    first_day, last_day, ndays = _month_bounds(rok, mesic)
    holidays = _cz_holidays(rok)

    vykazy = ZakazkaZamestnanec.objects.filter(
        zamestnanec=zam, den_prace__gte=first_day, den_prace__lte=last_day
    )

    actual_total = sum(
        (Decimal(str(_hours_between(v.den_prace, v.cas_od, v.cas_do))) for v in vykazy),
        Decimal("0.0")
    )
    plan_total = sum(
        (Decimal(str(_plan_for_day_custom(zam, first_day + dt.timedelta(days=i), holidays)))
         for i in range(ndays)),
        Decimal("0.0")
    )
    delta = actual_total - plan_total

    UzaverkaMesice.objects.create(zamestnanec=zam, rok=rok, mesic=mesic, delta_hodin=delta)
    try:
        # pokud má Zamestnanec pole banka_hodin (Decimal)
        zam.banka_hodin = (zam.banka_hodin or Decimal("0.0")) + delta
        zam.save(update_fields=["banka_hodin"])
    except Exception:
        # když pole neexistuje, tiše ignoruj
        pass

    messages.success(
        request,
        f"Uzavřeno. Rozdíl {delta:+.2f} h zapsán do banky hodin."
    )
    return redirect(f"{reverse('zamestnanec_timesheet', args=[zam.id])}?ym={_month_label(rok, mesic)}")

@login_required
def otevrit_mesic_view(request, zamestnanec_id: int, rok: int, mesic: int):
    """
    Zruší uzavření měsíce (rollback).
    Smaže záznam v UzaverkaMesice a odečte delta_hodin z banky hodin zaměstnance.
    """
    if not request.user.is_admin:
        return HttpResponseForbidden("Pouze administrátor může měnit uzavření měsíců.")

    zam = get_object_or_404(Zamestnanec, pk=zamestnanec_id)
    rok = int(rok); mesic = int(mesic)

    rec = UzaverkaMesice.objects.filter(zamestnanec=zam, rok=rok, mesic=mesic).first()
    if not rec:
        messages.info(request, "Tento měsíc není uzavřen — není co zrušit.")
        return redirect(f"{reverse('zamestnanec_timesheet', args=[zam.id])}?ym={_month_label(rok, mesic)}")

    delta = rec.delta_hodin  # Decimal
    with transaction.atomic():
        rec.delete()
        try:
            zam.banka_hodin = (zam.banka_hodin or Decimal("0.0")) - delta
            zam.save(update_fields=["banka_hodin"])
        except Exception:
            # pokud by pole nebylo, tiše ignorujeme (jako v uzavření)
            pass

    messages.success(request, f"Uzavření zrušeno. Úprava banky hodin: {delta:+.2f} h byla vrácena.")
    return redirect(f"{reverse('zamestnanec_timesheet', args=[zam.id])}?ym={_month_label(rok, mesic)}")


_WD_MAP = ["po", "ut", "st", "ct", "pa", "so", "ne"]

def _weekly_plan_hours(zam: Zamestnanec, d: dt.date) -> Decimal:
    fld = f"plan_{_WD_MAP[d.weekday()]}"
    val = getattr(zam, fld, 8 if d.weekday() < 5 else 0)
    return Decimal(str(val))

def _plan_for_day_custom(zam: Zamestnanec, d: dt.date, holidays: set[dt.date]) -> Decimal:
    """
    Výchozí: týdenní šablona; státní svátky = 0 h.
    Když existuje PlanDen override, ten má přednost (může být i 0).
    """
    base = Decimal("0.0") if d in holidays else _weekly_plan_hours(zam, d)
    ov = PlanDen.objects.filter(zamestnanec=zam, datum=d).values_list("plan_hodin", flat=True).first()
    return Decimal(str(ov)) if ov is not None else base

@require_POST
@login_required
@csrf_protect
def ulozit_plan_mesice_view(request, zamestnanec_id: int):
    if not request.user.is_admin:
        return HttpResponseForbidden("Pouze administrátor může upravit plán hodin.")

    zam = get_object_or_404(Zamestnanec, pk=zamestnanec_id)
    ym = request.GET.get("ym")
    if not ym:
        return redirect(reverse("zamestnanec_timesheet", args=[zam.id]))

    year, month = map(int, ym.split("-"))
    first_day, last_day, ndays = _month_bounds(year, month)
    holidays = _cz_holidays(year)

    # uložit každé pole plan_1..plan_ndays
    for i in range(1, ndays + 1):
        key = f"plan_{i}"
        if key not in request.POST:
            continue
        raw = request.POST.get(key, "").strip()
        if raw == "":
            continue
        try:
            val = Decimal(raw)
            if val < 0 or val > 24:
                continue
        except Exception:
            continue

        d = first_day + dt.timedelta(days=i - 1)

        # pokud hodnota odpovídá výchozímu plánu, override smažeme
        base = _plan_for_day_custom(zam, d, holidays)
        if val == base:
            PlanDen.objects.filter(zamestnanec=zam, datum=d).delete()
        else:
            PlanDen.objects.update_or_create(
                zamestnanec=zam, datum=d, defaults={"plan_hodin": val}
            )

    return redirect(f"{reverse('zamestnanec_timesheet', args=[zam.id])}?ym={ym}")

@login_required
@csrf_protect
def employee_weekly_plan_view(request, zamestnanec_id):
    if not request.user.is_admin:
        return HttpResponseForbidden("Pouze administrátor může upravit týdenní plán.")

    zam = get_object_or_404(Zamestnanec, id=zamestnanec_id)

    if request.method == "POST":
        form = EmployeeWeeklyPlanForm(request.POST, instance=zam)
        if form.is_valid():
            form.save()
            messages.success(request, "Týdenní plán byl uložen.")
            # po uložení zpět na detail zaměstnance v homepage s otevřeným panelem
            return redirect(f'/homepage/?detail_zamestnanec={zam.id}')
    else:
        form = EmployeeWeeklyPlanForm(instance=zam)

    return render(request, "employee_weekly_plan_form.html", {
        "form": form,
        "zamestnanec": zam,
    })

@login_required
def statistiky_view(request):
    """
    Dashboard statistik (jen pro admina)

    Režimy:
      - scope=month (default) + ym=YYYY-MM
      - scope=year          + y=YYYY
      - scope=all           (od prvního záznamu do dneška)

    Vždy:
      - Pokud období končí v aktuálním měsíci, počítá se jen DO DNEŠKA (včetně).
      - Mzdy zaměstnanců se prorátují po jednotlivých MĚSÍCÍCH podle podílu
        pracovních dní zahrnutých v daném měsíci (Po–Pá, bez svátků).
      - Výnosy = sazba zakázky × hodiny z výkazů.
      - Externista = hodiny × jeho hodinová sazba.
      - Režie = součet přes pracovní dny (Po–Pá, bez svátků) 8 h × sazba v daný den.
      - Rozpady (zaměstnanci/zakázky/klienti) jsou BEZ režie.
    """
    if not request.user.is_admin:
        return HttpResponseForbidden("Pouze administrátor může zobrazit statistiky.")

    scope = request.GET.get("scope", "month").lower().strip()

    # --- určení období -------------------------------------------------------
    today_local = localdate()

    def month_bounds(y: int, m: int) -> tuple[dt.date, dt.date, int]:
        nd = calendar.monthrange(y, m)[1]
        return dt.date(y, m, 1), dt.date(y, m, nd), nd

    if scope == "year":
        y_param = request.GET.get("y")
        if y_param:
            year = int(y_param)
        else:
            year = today_local.year
        first_day = dt.date(year, 1, 1)
        last_day = dt.date(year, 12, 31)
        # omezení do dneška u aktuálního roku
        period_end = min(last_day, today_local) if year == today_local.year else last_day
        nav_prev = f"{year-1}"
        nav_next = f"{year+1}"
        year_for_holidays = range(first_day.year, period_end.year + 1)

    elif scope == "all":
        # od nejstaršího výkazu do dneška
        first = ZakazkaZamestnanec.objects.order_by("den_prace").values_list("den_prace", flat=True).first()
        if first is None:
            # fallback: prázdná DB – ber dnešek
            first_day = period_end = last_day = today_local
        else:
            first_day = first
            last_day = today_local  # „kalendářní konec“ tady není relevantní
            period_end = today_local
        nav_prev = nav_next = None
        year_for_holidays = range(first_day.year, period_end.year + 1)

    else:  # scope == "month" (default)
        ym = request.GET.get("ym")
        if ym:
            y, m = map(int, ym.split("-"))
        else:
            y, m = today_local.year, today_local.month
        first_day, last_day, _ = month_bounds(y, m)
        # omezení do dneška u aktuálního měsíce
        period_end = min(last_day, today_local) if (y == today_local.year and m == today_local.month) else last_day
        (prev_y, prev_m), (next_y, next_m) = _month_nav(y, m)
        nav_prev = f"{prev_y:04d}-{prev_m:02d}"
        nav_next = f"{next_y:04d}-{next_m:02d}"
        year_for_holidays = [y]  # jen tento rok

    # pomocné počty dní
    days_in_scope = (period_end - first_day).days + 1

    # --- svátky přes VŠECHNY roky v rozsahu ----------------------------------
    holidays: set[dt.date] = set()
    for y in year_for_holidays:
        holidays |= _cz_holidays(y)

    def is_workday(d: dt.date) -> bool:
        return (d.weekday() < 5) and (d not in holidays)

    # --- helper pro iteraci měsíců v libovolném rozsahu ----------------------
    def iter_months(start: dt.date, end: dt.date):
        y, m = start.year, start.month
        while True:
            ms, ml, _ = month_bounds(y, m)
            yield (y, m, ms, ml)
            if ml >= end:
                break
            # posun na další měsíc
            if m == 12:
                y += 1; m = 1
            else:
                m += 1
            if dt.date(y, m, 1) > end:
                break

    # --- helper: režijní sazba v den (fallback 0, pokud helper nemáš) -------
    def _over_on(day: dt.date) -> Decimal:
        try:
            return Decimal(str(_overhead_rate_on(day)))
        except NameError:
            return Decimal("0.0")

    # --- výkazy v období ------------------------------------------------------
    qs = (
        ZakazkaZamestnanec.objects
        .filter(den_prace__gte=first_day, den_prace__lte=period_end)
        .select_related("zakazka", "zamestnanec", "zakazka__klient", "zakazka__sazba")
        .order_by("den_prace")
    )

    # kumulátory
    total_hours = Decimal("0.0")
    total_km = Decimal("0.0")
    labor_cost_external_total = Decimal("0.0")  # externisté: hodiny × sazba_hod
    travel_cost_total = Decimal("0.0")
    revenue_total = Decimal("0.0")

    # rozpady (bez režie)
    by_employee, by_project, by_client = {}, {}, {}

    # podklady pro alokaci mezd zaměstnanců (podle hodin v OBDOBÍ)
    emp_total_hours: dict[int, Decimal] = {}
    emp_proj_hours: dict[tuple[int, int], Decimal] = {}
    emp_client_hours: dict[tuple[int, int], Decimal] = {}

    for v in qs:
        hrs = Decimal(str(_hours_between(v.den_prace, v.cas_od, v.cas_do)))
        if hrs <= 0:
            continue
        km = Decimal(str(v.najete_km or 0))

        emp = v.zamestnanec
        proj = v.zakazka
        cli = getattr(proj, "klient", None)

        # cestovní náklady
        rate_km = Decimal(str(emp.sazba_km or 0))
        travel_cost = km * rate_km

        # výnos
        proj_rate = Decimal(str(proj.sazba.hodnota)) if getattr(proj, "sazba", None) and proj.sazba.hodnota is not None else Decimal("0.0")
        revenue = hrs * proj_rate

        total_hours += hrs
        total_km += km
        travel_cost_total += travel_cost
        revenue_total += revenue

        # mzdové: externista přímo hodinovkou, zaměstnanec až v alokaci mezd
        if getattr(emp, "typ_osoby", None) == Zamestnanec.TYP_EXTERNAL:
            rate_h = Decimal(str(emp.sazba_hod or 0))
            labor_cost = hrs * rate_h
        else:
            labor_cost = Decimal("0.0")

        # pro alokaci mezd
        emp_total_hours[emp.id] = emp_total_hours.get(emp.id, Decimal("0.0")) + hrs
        emp_proj_hours[(emp.id, proj.id)] = emp_proj_hours.get((emp.id, proj.id), Decimal("0.0")) + hrs
        if cli:
            emp_client_hours[(emp.id, cli.id)] = emp_client_hours.get((emp.id, cli.id), Decimal("0.0")) + hrs

        # by employee
        be = by_employee.setdefault(emp.id, {
            "emp": emp,
            "hours": Decimal("0.0"), "km": Decimal("0.0"),
            "labor_cost": Decimal("0.0"), "travel_cost": Decimal("0.0"),
            "total_cost": Decimal("0.0"), "revenue": Decimal("0.0"),
            "margin": Decimal("0.0"),
        })
        be["hours"] += hrs
        be["km"] += km
        be["travel_cost"] += travel_cost
        be["labor_cost"] += labor_cost
        be["total_cost"] += (labor_cost + travel_cost)
        be["revenue"] += revenue
        be["margin"] += (revenue - (labor_cost + travel_cost))

        # by project
        bp = by_project.setdefault(proj.id, {
            "zakazka": proj,
            "hours": Decimal("0.0"), "km": Decimal("0.0"),
            "total_cost": Decimal("0.0"), "revenue": Decimal("0.0"),
            "margin": Decimal("0.0"),
        })
        bp["hours"] += hrs
        bp["km"] += km
        bp["total_cost"] += (labor_cost + travel_cost)
        bp["revenue"] += revenue
        bp["margin"] += (revenue - (labor_cost + travel_cost))

        # by client
        if cli:
            bc = by_client.setdefault(cli.id, {
                "klient": cli,
                "hours": Decimal("0.0"),
                "total_cost": Decimal("0.0"), "revenue": Decimal("0.0"),
                "margin": Decimal("0.0"),
            })
            bc["hours"] += hrs
            bc["total_cost"] += (labor_cost + travel_cost)
            bc["revenue"] += revenue
            bc["margin"] += (revenue - (labor_cost + travel_cost))

    # --- mzdy zaměstnanců: PRORÁTA po měsících v rozsahu ---------------------
    employees = list(Zamestnanec.objects.filter(is_active=True, typ_osoby=Zamestnanec.TYP_EMPLOYEE))
    salary_by_emp: dict[int, Decimal] = {e.id: Decimal("0.0") for e in employees}

    for (y, m, ms, ml) in iter_months(first_day, period_end):
        month_scope_start = max(first_day, ms)
        month_scope_end   = min(period_end, ml)

        # pracovní dny v CELÉM měsíci a v jeho zahrnuté části
        total_workdays_month = sum(1 for i in range((ml - ms).days + 1) if is_workday(ms + dt.timedelta(days=i)))
        workdays_in_scope    = sum(1 for i in range((month_scope_end - month_scope_start).days + 1)
                                   if is_workday(month_scope_start + dt.timedelta(days=i)))

        ratio = (Decimal(workdays_in_scope) / Decimal(total_workdays_month)) if total_workdays_month else Decimal("0.0")

        if ratio > 0:
            for emp in employees:
                mzda = Decimal(str(emp.mzda_mesic or 0))
                salary_by_emp[emp.id] += (mzda * ratio)

    # sečti mzdy a zapiš do by_employee + alokuj do projektů/klientů podle hodin
    salary_total = sum(salary_by_emp.values(), Decimal("0.0"))
    for emp in employees:
        mzda_emp = salary_by_emp.get(emp.id, Decimal("0.0"))
        if mzda_emp <= 0:
            continue

        be = by_employee.setdefault(emp.id, {
            "emp": emp,
            "hours": Decimal("0.0"), "km": Decimal("0.0"),
            "labor_cost": Decimal("0.0"), "travel_cost": Decimal("0.0"),
            "total_cost": Decimal("0.0"), "revenue": Decimal("0.0"),
            "margin": Decimal("0.0"),
        })
        be["labor_cost"] += mzda_emp
        be["total_cost"] += mzda_emp
        be["margin"] -= mzda_emp

        emp_hours = emp_total_hours.get(emp.id, Decimal("0.0"))
        if emp_hours > 0:
            # rozdělení mzdy mezi projekty/klienty
            for (e_id, proj_id), h in emp_proj_hours.items():
                if e_id != emp.id or h <= 0:
                    continue
                share = (h / emp_hours) * mzda_emp
                bp = by_project.get(proj_id)
                if bp:
                    bp["total_cost"] += share
                    bp["margin"] -= share
                    proj = bp["zakazka"]
                    cli = getattr(proj, "klient", None)
                    if cli:
                        bc = by_client.get(cli.id)
                        if bc:
                            bc["total_cost"] += share
                            bc["margin"] -= share
        # pokud nemá hodiny, mzda zůstává jen na řádku zaměstnance (bez „nealokované“ položky)

    # --- plán hodin v období (součet přes zaměstnance) ------------------------
    plan_total = Decimal("0.0")
    active_emps = Zamestnanec.objects.filter(is_active=True)
    for emp in active_emps:
        for i in range(days_in_scope):
            dte = first_day + dt.timedelta(days=i)
            try:
                plan_i = _plan_for_day_custom(emp, dte, holidays)
            except NameError:
                plan_i = _plan_for_day(dte, holidays)
            plan_total += Decimal(str(plan_i))
    diff_total = (total_hours - plan_total)

    # --- režie jen do period_end ---------------------------------------------
    overhead_total = Decimal("0.0")
    for i in range(days_in_scope):
        d = first_day + dt.timedelta(days=i)
        if d.weekday() < 5 and d not in holidays:
            overhead_total += Decimal("8.0") * _over_on(d)

    # interní náklady a marže
    labor_cost_total = (labor_cost_external_total + salary_total)
    internal_cost_total = (labor_cost_external_total + salary_total + travel_cost_total + overhead_total)
    margin_total = (revenue_total - internal_cost_total)

    # KPI počty
    kpi = {
        "projects_active": Zakazka.objects.filter(zakazka_konec_skut__isnull=True).count(),
        "employees_active": active_emps.count(),
        "clients": Klient.objects.count(),
        "subdodavatels": Subdodavatel.objects.count(),
    }

    # seřazení tabulek
    by_emp = sorted(by_employee.values(), key=lambda x: (x["total_cost"], x["hours"]), reverse=True)
    by_proj = sorted(by_project.values(),  key=lambda x: (x["total_cost"], x["hours"]), reverse=True)
    by_cli  = sorted(by_client.values(),   key=lambda x: (x["revenue"], x["hours"]), reverse=True)

    # přehled nových/ukončených zakázek v období
    new_projects = (
        Zakazka.objects
        .filter(zakazka_start__date__gte=first_day, zakazka_start__date__lte=period_end)
        .order_by("zakazka_start")
    )
    closed_projects = (
        Zakazka.objects
        .filter(zakazka_konec_skut__date__gte=first_day, zakazka_konec_skut__date__lte=period_end)
        .order_by("zakazka_konec_skut")
    )

    context = {
        "scope": scope,
        # pro month
        "ym": f"{first_day.year:04d}-{first_day.month:02d}" if scope == "month" else "",
        "prev_ym": nav_prev if scope == "month" else "",
        "next_ym": nav_next if scope == "month" else "",
        # pro year
        "y": first_day.year if scope != "all" else "",
        "prev_y": nav_prev if scope == "year" else "",
        "next_y": nav_next if scope == "year" else "",

        "first_day": first_day,
        "last_day": last_day,
        "calc_until": period_end,

        "kpi": kpi,
        "total_hours": total_hours,
        "total_km": total_km,
        "plan_total": plan_total,
        "diff_total": diff_total,

        "salary_total": salary_total,
        "labor_cost_external_total": labor_cost_external_total,
        "travel_cost_total": travel_cost_total,
        "overhead_total": overhead_total,
        "labor_cost_total": labor_cost_total,
        "internal_cost_total": internal_cost_total,
        "revenue_total": revenue_total,
        "margin_total": margin_total,

        "new_projects": new_projects,
        "closed_projects": closed_projects,

        "by_emp": by_emp,
        "by_proj": by_proj,
        "by_client": by_cli,
    }
    return render(request, "statistiky.html", context)



@login_required
@csrf_protect
def overhead_list_create_view(request):
    if not request.user.is_admin:
        return HttpResponseForbidden("Pouze administrátor může spravovat režijní náklady.")
    form = OverheadRateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Režijní sazba byla uložena.")
        return redirect("overhead_list")
    rates = OverheadRate.objects.all()  # ordered by -valid_from
    return render(request, "overhead_list.html", {"form": form, "rates": rates})

@login_required
@csrf_protect
def overhead_edit_view(request, rate_id):
    if not request.user.is_admin:
        return HttpResponseForbidden("Pouze administrátor může spravovat režijní náklady.")
    rate = get_object_or_404(OverheadRate, id=rate_id)
    form = OverheadRateForm(request.POST or None, instance=rate)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Režijní sazba byla upravena.")
        return redirect("overhead_list")
    return render(request, "overhead_edit.html", {"form": form, "rate": rate})

def _overhead_rate_on(day: dt.date) -> Decimal:
    """
    Vrátí režijní sazbu (Kč/h) platnou v daný den. Když není žádná, vrací 0.
    """
    rec = OverheadRate.objects.filter(valid_from__lte=day).order_by("-valid_from").first()
    return Decimal(str(rec.rate_per_hour)) if rec else Decimal("0.00")