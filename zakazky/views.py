# views.py
from collections import defaultdict

from django.apps import apps
from django.db import transaction
from django.forms import modelformset_factory
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.template.defaultfilters import date
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.contrib.auth.forms import PasswordChangeForm
from .helpers import _hours_between, overhead_worker_hour
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
from decimal import Decimal, ROUND_HALF_UP
from .helpers import planned_hours, overhead_rate_on, _hours_between
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


def _fmt_hhmm_from_hours(h: Decimal) -> str:
    # bezpečně i pro None
    h = Decimal("0") if h is None else Decimal(str(h))
    total_minutes = int((h * Decimal("60")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    hh = total_minutes // 60
    mm = total_minutes % 60
    return f"{hh:02d}:{mm:02d}"


@login_required
def homepage_view(request):
    # --- levý sloupec: seznam zakázek ---------------------------------------
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

    # --- pravý panel: výběry detailů -----------------------------------------
    selected_zamestnanec_id = request.GET.get("detail_zamestnanec")
    zamestnanec_sidebar = Zamestnanec.objects.filter(id=selected_zamestnanec_id).first() if selected_zamestnanec_id else None

    selected_subdodavatel_id = request.GET.get("detail_subdodavatel")
    subdodavatel_sidebar = Subdodavatel.objects.filter(id=selected_subdodavatel_id).first() if selected_subdodavatel_id else None

    selected_subdodavka_id = request.GET.get("detail_subdodavka")
    subdodavka_sidebar = Subdodavka.objects.filter(id=selected_subdodavka_id).first() if selected_subdodavka_id else None

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
    klient_poznamky = KlientPoznamka.objects.filter(klient_id=selected_klient_id).order_by('-datum') if selected_klient_id else None

    uredni_zapisy = UredniZapis.objects.filter(zakazka=zakazka_detail) if zakazka_detail else None
    rozsahy_prace = RozsahPrace.objects.filter(zakazka=zakazka_detail) if zakazka_detail else None

    zamestnanec_filter_id = request.GET.get("vykazy_zamestnanec")
    vykazy = None
    if zakazka_detail:
        vykazy_qs = zakazka_detail.zakazkazamestnanec_set.all()
        if zamestnanec_filter_id:
            vykazy_qs = vykazy_qs.filter(zamestnanec_id=zamestnanec_filter_id)
        vykazy = vykazy_qs.select_related('zamestnanec').order_by('-den_prace')

    # --- subdodávky fakturované Arched ---------------------------------------
    arched_subs_count = 0
    arched_subs_sum = Decimal("0")
    if zakazka_detail:
        arched_subs = ZakazkaSubdodavka.objects.filter(zakazka=zakazka_detail, fakturuje_arched=True)
        arched_subs_count = arched_subs.count()
        arched_subs_sum = arched_subs.aggregate(Sum('cena'))['cena__sum'] or Decimal("0")

    # --- progress bar hodin u zakázky ----------------------------------------
    odpracovano_hodin = 0.0
    zbyva_hodin = 0.0
    barva_zbyva = "success"
    progress_percent = 0.0
    predpokladany_cas = 0.0

    if zakazka_detail:
        vykazy_qs = zakazka_detail.zakazkazamestnanec_set.all()

        if request.user.is_admin:
            relevantni_vykazy = vykazy_qs
            predpokladany_cas = float(zakazka_detail.predpokladany_cas or 0)
        else:
            relevantni_vykazy = vykazy_qs.filter(zamestnanec=request.user)
            predpokladany_cas = float(
                ZamestnanecZakazka.objects.filter(zakazka=zakazka_detail, zamestnanec=request.user)
                .aggregate(Sum('prideleno_hodin'))['prideleno_hodin__sum'] or 0
            )

        for v in relevantni_vykazy:
            if v.cas_od and v.cas_do:
                dt_od = datetime.combine(v.den_prace, v.cas_od)
                dt_do = datetime.combine(v.den_prace, v.cas_do)
                diff = dt_do - dt_od
                odpracovano_hodin += max(diff.total_seconds() / 3600.0, 0.0)

        zbyva_hodin = predpokladany_cas - odpracovano_hodin
        podil = (zbyva_hodin / predpokladany_cas) if predpokladany_cas > 0 else 1

        if podil <= 0:
            barva_zbyva = "danger"
        elif podil <= 0.1:
            barva_zbyva = "warning"
        else:
            barva_zbyva = "success"

        if predpokladany_cas > 0:
            progress_percent = min(100.0, (odpracovano_hodin / predpokladany_cas) * 100.0)

    # --- výnosy (sazba × hodiny) pro admina ----------------------------------
    proj_rate = None
    rev_actual = None
    rev_plan = None
    if request.user.is_admin and zakazka_detail and getattr(zakazka_detail, "sazba_id", None):
        try:
            rate = Decimal(str(zakazka_detail.sazba.hodnota))
            hours_all = Decimal("0")
            for v in zakazka_detail.zakazkazamestnanec_set.all():
                if v.cas_od and v.cas_do:
                    dt_od = datetime.combine(v.den_prace, v.cas_od)
                    dt_do = datetime.combine(v.den_prace, v.cas_do)
                    secs = max((dt_do - dt_od).total_seconds(), 0.0)
                    hours_all += Decimal(str(secs / 3600.0))
            proj_rate = rate
            rev_actual = (rate * hours_all).quantize(Decimal("0.01"))
            plan_hours = Decimal(str(zakazka_detail.predpokladany_cas or 0))
            rev_plan = (rate * plan_hours).quantize(Decimal("0.01"))
        except Exception:
            proj_rate = None
            rev_actual = None
            rev_plan = None

    # --- historie (pokud používáš simple_history) ----------------------------
    historie_urednich_zaznamu = None
    historie_vykazu_prace = None
    if zakazka_detail:
        uredni_ids = UredniZapis.objects.filter(zakazka=zakazka_detail).values_list('id', flat=True)
        from simple_history.utils import get_history_model_for_model
        HistoryU = get_history_model_for_model(UredniZapis)
        historie_urednich_zaznamu = HistoryU.objects.filter(id__in=uredni_ids).order_by('-history_date')

        vykaz_ids = ZakazkaZamestnanec.objects.filter(zakazka=zakazka_detail).values_list('id', flat=True)
        HistoryV = get_history_model_for_model(ZakazkaZamestnanec)
        historie_vykazu_prace = HistoryV.objects.filter(id__in=vykaz_ids).order_by('-history_date')

    # --- Přiřazení zaměstnanci (opraveno: Decimal všude uvnitř výpočtu) ------
    prirazeni_vypocty = []
    if zamestnanci_prirazeni:
        for priraz in zamestnanci_prirazeni:
            prideleno_dec = Decimal(str(priraz.prideleno_hodin or 0))
            odpracovano_dec = Decimal("0")

            vqs = ZakazkaZamestnanec.objects.filter(
                zakazka=zakazka_zam,
                zamestnanec=priraz.zamestnanec
            )
            for v in vqs:
                if v.cas_od and v.cas_do:
                    # spočítej přesně v sekundách -> Decimal hodin
                    dt_od = datetime.combine(v.den_prace, v.cas_od)
                    dt_do = datetime.combine(v.den_prace, v.cas_do)
                    secs = max((dt_do - dt_od).total_seconds(), 0.0)
                    odpracovano_dec += Decimal(str(secs / 3600.0))

            zbyva_dec = prideleno_dec - odpracovano_dec

            if prideleno_dec > 0:
                podil = zbyva_dec / prideleno_dec
            else:
                podil = Decimal("1")

            if podil <= Decimal("0"):
                barva = "danger"
            elif podil <= Decimal("0.1"):
                barva = "warning"
            else:
                barva = "success"

            vidi = priraz.datum_prideleni and priraz.datum_prideleni <= now() and not priraz.skryta
            datum_ok = priraz.datum_prideleni and priraz.datum_prideleni <= now()

            # do šablony pošleme floaty (formátuješ vlastními filtry)
            prirazeni_vypocty.append({
                'prirazeni': priraz,
                'prideleno': float(prideleno_dec),
                'odpracovano': float(odpracovano_dec.quantize(Decimal("0.1"))),
                'zbyva': float(zbyva_dec.quantize(Decimal("0.1"))),
                'barva': barva,
                'skryta': priraz.skryta,
                'vidi': vidi,
                'datum_ok': datum_ok,
            })

    # --- FINANCE ZAKÁZKY: kompletní rekapitulace do off-canvas ---------------
    project_finance = None
    if request.user.is_admin and zakazka_detail:
        try:
            project_finance = _project_finance_for(zakazka_detail)
        except Exception:
            project_finance = None

    # --- kontext do šablony ---------------------------------------------------
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
        'zamestnanci_v_zakazce': ZakazkaZamestnanec.objects.filter(zakazka=zakazka_detail)
            .values_list('zamestnanec__id', 'zamestnanec__jmeno', 'zamestnanec__prijmeni').distinct(),
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

        # >>> NOVÉ <<<
        'project_finance': project_finance,
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
    Timesheet zaměstnance:
      - sloupce: dny v měsíci (víkend/svátek barevně)
      - řádky: zakázky (hodiny/den), na konci řádku součet hodin + součet KM za měsíc
      - dole: součet dne, plán dne, denní rozdíl, měsíční součty
      - respektuje individuální plán dne (PlanDen) a trvalý týdenní plán ze Zamestnanec
    """
    from decimal import Decimal
    import datetime as dt, calendar
    from django.db.models import Sum
    from django.shortcuts import get_object_or_404, render
    from .models import ZakazkaZamestnanec, Zamestnanec, UzaverkaMesice, PlanDen

    zam = get_object_or_404(Zamestnanec, pk=zamestnanec_id)

    # vybraný měsíc
    ym = request.GET.get("ym")
    if ym:
        year, month = map(int, ym.split("-"))
    else:
        today = now().date()
        year, month = today.year, today.month

    # hranice měsíce
    ndays = calendar.monthrange(year, month)[1]
    first_day = dt.date(year, month, 1)
    last_day = dt.date(year, month, ndays)

    # svátky
    holidays = _cz_holidays(year)

    # --- 1) Individuální plán dne (měsíční override z PlanDen.plan_hodin) ---
    ov_qs = PlanDen.objects.filter(
        zamestnanec=zam,
        datum__gte=first_day,
        datum__lte=last_day
    ).values("datum", "plan_hodin")
    overrides = {o["datum"]: Decimal(str(o["plan_hodin"] or 0)) for o in ov_qs}

    # --- 2) Trvalý týdenní plán (Po..Ne) ze zaměstnance ----------------------
    def _weekly_plan_for(z):
        fields = ("plan_po","plan_ut","plan_st","plan_ct","plan_pa","plan_so","plan_ne")
        vals = []
        for f in fields:
            v = getattr(z, f, None)
            vals.append(Decimal(str(v)) if v is not None else None)
        return vals

    weekly = _weekly_plan_for(zam)

    # --- výkazy v měsíci ------------------------------------------------------
    qs = (
        ZakazkaZamestnanec.objects
        .filter(zamestnanec=zam, den_prace__gte=first_day, den_prace__lte=last_day)
        .select_related("zakazka")
        .order_by("zakazka__zakazka_cislo", "den_prace")
    )

    # stabilní pořadí zakázek
    zakazky_order, seen = [], set()
    for v in qs:
        if v.zakazka_id not in seen:
            zakazky_order.append(v.zakazka)
            seen.add(v.zakazka_id)

    # mřížka hodin (po dnech) + km součty po zakázkách
    grid_hours = {z.id: [Decimal("0.0")] * ndays for z in zakazky_order}
    proj_km = {z.id: Decimal("0.0") for z in zakazky_order}

    for v in qs:
        idx = (v.den_prace - first_day).days
        hrs = Decimal(str(_hours_between(v.den_prace, v.cas_od, v.cas_do)))
        grid_hours.setdefault(v.zakazka_id, [Decimal("0.0")] * ndays)
        grid_hours[v.zakazka_id][idx] += hrs

        km = Decimal(str(v.najete_km or 0))
        proj_km[v.zakazka_id] = proj_km.get(v.zakazka_id, Decimal("0.0")) + km

    # pomocná: plán pro konkrétní den (override > svátek=0 > týdenní plán > default)
    def plan_for_day(d: dt.date) -> Decimal:
        if d in overrides:
            return overrides[d]
        if d in holidays:
            return Decimal("0.0")
        w = d.weekday()  # 0=Po .. 6=Ne
        base = weekly[w]
        if base is not None:
            return base
        return Decimal("8.0") if w < 5 else Decimal("0.0")

    # denní součty, plán a rozdíl
    sum_by_day = [Decimal("0.0")] * ndays
    plan_by_day = [Decimal("0.0")] * ndays
    days_meta = []

    for i in range(ndays):
        dte = first_day + dt.timedelta(days=i)
        weekend = dte.weekday() >= 5
        holiday = dte in holidays

        total_d = sum((grid_hours[zid][i] for zid in grid_hours), Decimal("0.0"))
        plan_i = plan_for_day(dte)
        diff_i = total_d - plan_i

        sum_by_day[i] = total_d
        plan_by_day[i] = plan_i

        days_meta.append({
            "date": dte,
            "num": i + 1,
            "weekend": weekend,
            "holiday": holiday,
            "sum": total_d,      # formátování do HH:MM nechte na šabloně (filtr)
            "plan": plan_i,
            "diff": diff_i,
            "diff_pos": diff_i > 0,
            "diff_neg": diff_i < 0,
        })

    # řádky tabulky (hodiny po dnech + součet hodin + součet km)
    rows = []
    month_total_hours = Decimal("0.0")
    month_total_km = Decimal("0.0")

    for z in zakazky_order:
        vals = grid_hours.get(z.id, [Decimal("0.0")] * ndays)
        row_total = sum(vals, Decimal("0.0"))
        row_km = proj_km.get(z.id, Decimal("0.0"))

        cells = [{
            "value": vals[i],
            "weekend": days_meta[i]["weekend"],
            "holiday": days_meta[i]["holiday"],
        } for i in range(ndays)]

        rows.append({
            "zakazka": z,
            "cells": cells,
            "total": row_total,
            "km_total": row_km,
        })

        month_total_hours += row_total
        month_total_km += row_km

    plan_total = sum(plan_by_day, Decimal("0.0"))
    diff_total = (month_total_hours - plan_total)

    # banka hodin
    bank_now = getattr(zam, "banka_hodin", None)
    if bank_now is None:
        bank_now = UzaverkaMesice.objects.filter(zamestnanec=zam).aggregate(s=Sum("delta_hodin"))["s"] or Decimal("0.0")
    elif not isinstance(bank_now, Decimal):
        bank_now = Decimal(str(bank_now))

    closed_rec = UzaverkaMesice.objects.filter(zamestnanec=zam, rok=year, mesic=month).first()
    month_closed = bool(closed_rec)
    projected_bank = bank_now if month_closed else (bank_now + diff_total)

    # šipková navigace
    prev_y, prev_m = _month_nav(year, month)[0]
    next_y, next_m = _month_nav(year, month)[1]
    prev_ym = f"{prev_y:04d}-{prev_m:02d}"
    next_ym = f"{next_y:04d}-{next_m:02d}"

    context = {
        "zamestnanec": zam,
        "year": year, "month": month,
        "ym": f"{year:04d}-{month:02d}",
        "prev_ym": prev_ym, "next_ym": next_ym,
        "first_day": first_day, "last_day": last_day,

        "days": days_meta,
        "rows": rows,
        "plan_total": plan_total,
        "month_total": month_total_hours,
        "diff_total": diff_total,

        "month_km_total": month_total_km,

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
    if not request.user.is_admin:
        return HttpResponseForbidden("Pouze administrátor může zobrazit statistiky.")

    ZERO = Decimal("0")

    # --- helpers --------------------------------------------------------------
    def month_bounds(y: int, m: int):
        last = calendar.monthrange(y, m)[1]
        return dt.date(y, m, 1), dt.date(y, m, last)

    def month_nav(y: int, m: int):
        prev_y, prev_m = (y - 1, 12) if m == 1 else (y, m - 1)
        next_y, next_m = (y + 1, 1) if m == 12 else (y, m + 1)
        return f"{prev_y:04d}-{prev_m:02d}", f"{next_y:04d}-{next_m:02d}"

    today = localdate()
    scope = (request.GET.get("scope") or "month").lower()

    # --- období ---------------------------------------------------------------
    prev_ym = next_ym = prev_y = next_y = ""
    if scope == "year":
        year = int(request.GET.get("y") or today.year)
        first_day = dt.date(year, 1, 1)
        last_day  = dt.date(year, 12, 31)
        calc_until = min(last_day, today) if year == today.year else last_day
        prev_y, next_y = str(year - 1), str(year + 1)
        y_for_template, ym_for_template = year, ""
    elif scope == "all":
        first_v = ZakazkaZamestnanec.objects.order_by("den_prace").values_list("den_prace", flat=True).first()
        first_day = first_v or today
        last_day = today
        calc_until = today
        y_for_template = ym_for_template = ""
    else:
        ym = request.GET.get("ym")
        if ym:
            y, m = map(int, ym.split("-"))
        else:
            y, m = today.year, today.month
        first_day, last_day = month_bounds(y, m)
        calc_until = min(last_day, today) if (y == today.year and m == today.month) else last_day
        prev_ym, next_ym = month_nav(y, m)
        y_for_template, ym_for_template = "", f"{y:04d}-{m:02d}"

    # --- efektivní hodinovka, pokud chybí sazba_hod ---------------------------
    def _effective_rate_h(emp, period_start: dt.date, period_end: dt.date) -> Decimal:
        """
        Hodinová sazba zaměstnance:
          - když má emp.sazba_hod > 0, použij ji,
          - jinak (měsíční mzda) / (plán hodin v období).
        """
        base = _as_dec(getattr(emp, "sazba_hod", 0), "0")
        if base > ZERO:
            return base

        plan_h = planned_hours(emp, period_start, period_end) or ZERO
        if plan_h <= ZERO:
            return ZERO

        monthly_fields = ("mzda_mesic", "mesicni_mzda", "mzda", "plat_mesic", "salary_monthly")
        monthly_wage = None
        for f in monthly_fields:
            if hasattr(emp, f):
                val = getattr(emp, f)
                if val is not None:
                    v = _as_dec(val, None)
                    if v is not None and v > ZERO:
                        monthly_wage = v
                        break

        if monthly_wage is None:
            return ZERO

        return (monthly_wage / plan_h).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # --- výkazy v období ------------------------------------------------------
    qs = (
        ZakazkaZamestnanec.objects
        .filter(den_prace__gte=first_day, den_prace__lte=calc_until)
        .select_related("zamestnanec", "zakazka", "zakazka__klient", "zakazka__sazba")
        .order_by("den_prace")
    )

    workh_by_emp: dict[int, Decimal] = {}
    km_by_emp: dict[int, Decimal] = {}

    for v in qs:
        hrs = _hours_between(v.den_prace, v.cas_od, v.cas_do)
        if not isinstance(hrs, Decimal):
            try:
                hrs = Decimal(str(hrs))
            except Exception:
                hrs = ZERO
        workh_by_emp[v.zamestnanec_id] = workh_by_emp.get(v.zamestnanec_id, ZERO) + hrs

        km = Decimal(str(v.najete_km or 0))
        km_by_emp[v.zamestnanec_id] = km_by_emp.get(v.zamestnanec_id, ZERO) + km

    # --- Mzdy zaměstnanci -----------------------------------------------------
    employees_rows = []
    oh_rate_today = overhead_rate_on(calc_until)  # Kč/h

    for emp in Zamestnanec.objects.filter(is_active=True, typ_osoby=Zamestnanec.TYP_EMPLOYEE):
        plan_h = planned_hours(emp, first_day, calc_until) or ZERO
        rate_h = _effective_rate_h(emp, first_day, calc_until)                 # Kč/h
        mzda = (plan_h * rate_h).quantize(Decimal("0.01"))

        km_sum  = km_by_emp.get(emp.id, ZERO)
        rate_km = Decimal(str(emp.sazba_km or 0))
        cestovne = (km_sum * rate_km).quantize(Decimal("0.01"))

        divisor = _as_dec(getattr(emp, "overhead_divisor", 1) or 1, "1")
        if divisor <= 0:
            divisor = Decimal("1")
        emp_oh = _as_dec(getattr(emp, "rezie_hod", 0) or 0, "0")               # osobní režie / hod

        celk_naklad_hod = (rate_h + (oh_rate_today / divisor) + emp_oh).quantize(Decimal("0.01"))
        celkem = (mzda + cestovne).quantize(Decimal("0.01"))

        employees_rows.append({
            "emp": emp,
            "plan_h": plan_h,
            "sazba_h": rate_h,
            "mzda": mzda,
            "km": km_sum,
            "sazba_km": rate_km,
            "cestovne": cestovne,
            "celkem": celkem,
            "celk_naklad_hod": celk_naklad_hod,
        })

    employees_total = sum((r["celkem"] for r in employees_rows), ZERO)

    # --- Externisté -----------------------------------------------------------
    externist_rows = []
    for emp in Zamestnanec.objects.filter(is_active=True, typ_osoby=Zamestnanec.TYP_EXTERNAL):
        hrs = workh_by_emp.get(emp.id, ZERO)
        rate_h = _effective_rate_h(emp, first_day, calc_until)
        castka = (hrs * rate_h).quantize(Decimal("0.01"))

        km_sum  = km_by_emp.get(emp.id, ZERO)
        rate_km = Decimal(str(emp.sazba_km or 0))
        cestovne = (km_sum * rate_km).quantize(Decimal("0.01"))

        divisor = _as_dec(getattr(emp, "overhead_divisor", 1) or 1, "1")
        if divisor <= 0:
            divisor = Decimal("1")
        emp_oh = _as_dec(getattr(emp, "rezie_hod", 0) or 0, "0")

        celk_naklad_hod = (rate_h + (oh_rate_today / divisor) + emp_oh).quantize(Decimal("0.01"))
        celkem = (castka + cestovne).quantize(Decimal("0.01"))

        externist_rows.append({
            "emp": emp,
            "hours": hrs,
            "rate_h": rate_h,
            "castka": castka,
            "km": km_sum,
            "rate_km": rate_km,
            "cestovne": cestovne,
            "celkem": celkem,
            "celk_naklad_hod": celk_naklad_hod,
        })

    externists_total = sum((r["celkem"] for r in externist_rows), ZERO)

    # --- Nové / ukončené zakázky ---------------------------------------------
    new_projects = (
        Zakazka.objects
        .filter(zakazka_start__date__gte=first_day, zakazka_start__date__lte=calc_until)
        .order_by("zakazka_start")
    )
    closed_projects = (
        Zakazka.objects
        .filter(zakazka_konec_skut__date__gte=first_day, zakazka_konec_skut__date__lte=calc_until)
        .order_by("zakazka_konec_skut")
    )

    # --- Výkony po zakázkách (v období) --------------------------------------
    projects_with_logs = (
        ZakazkaZamestnanec.objects
        .filter(den_prace__gte=first_day, den_prace__lte=calc_until)
        .values_list("zakazka_id", flat=True)
        .distinct()
    )

    all_logs_for_projects = (
        ZakazkaZamestnanec.objects
        .filter(zakazka_id__in=projects_with_logs)
        .select_related("zakazka", "zamestnanec", "zakazka__sazba")
        .order_by("zakazka_id", "den_prace", "cas_od", "cas_do")
    )

    # přednačti kapacity/sazby
    proj_caps: dict[int, Decimal]  = {}
    proj_rates: dict[int, Decimal] = {}
    for z in Zakazka.objects.filter(id__in=projects_with_logs).select_related("sazba"):
        cap = _as_dec(getattr(z, "predpokladany_cas", 0), "0")
        proj_caps[z.id] = cap if cap is not None else ZERO
        proj_rates[z.id] = _as_dec(getattr(getattr(z, "sazba", None), "hodnota", 0), "0")

    # kumulativní hodiny na projekt přes celé období (chronologicky)
    cum_hours_by_proj: dict[int, Decimal] = defaultdict(lambda: ZERO)

    # agregace pro šablonu: {proj_id: {emp_id: {emp, hours, naklady, vynosy, zisk}}}
    month_agg: dict[int, dict[int, dict]] = defaultdict(
        lambda: defaultdict(lambda: {"emp": None, "hours": ZERO, "naklady": ZERO, "vynosy": ZERO, "zisk": ZERO})
    )

    for v in all_logs_for_projects:
        proj_id = v.zakazka_id
        emp = v.zamestnanec

        h = _as_dec(_hours_between(v.den_prace, v.cas_od, v.cas_do), "0")
        if h <= ZERO:
            continue

        cap_total = proj_caps.get(proj_id, ZERO)
        proj_rate = proj_rates.get(proj_id, ZERO)

        rate_h = _effective_rate_h(emp, first_day, calc_until)
        divisor = _as_dec(getattr(emp, "overhead_divisor", 1) or 1, "1")
        if divisor <= ZERO:
            divisor = Decimal("1")
        try:
            oh_raw = overhead_rate_on(v.den_prace)  # firemní režie Kč/h
            oh_part = _as_dec(oh_raw, "0") / divisor
        except Exception:
            oh_part = ZERO
        emp_oh = _as_dec(getattr(emp, "rezie_hod", 0) or 0, "0")               # osobní režie Kč/h

        # allowed do stropu, overflow nad strop
        used_so_far = cum_hours_by_proj[proj_id]
        remaining = cap_total - used_so_far
        if remaining < ZERO:
            remaining = ZERO
        allowed = h if remaining >= h else (remaining if remaining > ZERO else ZERO)

        if first_day <= v.den_prace <= calc_until:
            # Výnosy jen z allowed:
            rev = (allowed * proj_rate)
            # Náklady za všechny hodiny: mzda + firemní OH/÷ + osobní režie
            cost = (h * (rate_h + oh_part + emp_oh))
            profit = (rev - cost)

            cell = month_agg[proj_id][emp.id]
            if cell["emp"] is None:
                cell["emp"] = emp
            cell["hours"]   += h
            cell["vynosy"]  += rev
            cell["naklady"] += cost
            cell["zisk"]    += profit

        # navýšime kumulativní hodiny projektu
        cum_hours_by_proj[proj_id] = used_so_far + h

    # převod pro šablonu
    month_tables: list[dict] = []
    if month_agg:
        z_map = {z.id: z for z in Zakazka.objects.filter(id__in=month_agg.keys()).select_related("klient")}
        for proj_id, rows in month_agg.items():
            z = z_map.get(proj_id)
            if not z:
                continue

            table_rows = []
            total_h = ZERO
            total_rev = ZERO
            total_cost = ZERO
            total_profit = ZERO

            for _emp_id, rec in rows.items():
                row = {
                    "emp": rec["emp"],
                    "hours": rec["hours"],
                    "vynosy": rec["vynosy"].quantize(Decimal("0.01")),
                    "naklady": rec["naklady"].quantize(Decimal("0.01")),
                    "zisk": rec["zisk"].quantize(Decimal("0.01")),
                }
                table_rows.append(row)
                total_h += rec["hours"]
                total_rev += row["vynosy"]
                total_cost += row["naklady"]
                total_profit += row["zisk"]

            table_rows.sort(key=lambda r: r["hours"], reverse=True)

            month_tables.append({
                "zakazka": z,
                "rows": table_rows,
                "total_hours": total_h,
                "total_vynosy": total_rev.quantize(Decimal("0.01")),
                "total_naklady": total_cost.quantize(Decimal("0.01")),
                "total_zisk": total_profit.quantize(Decimal("0.01")),
            })

        month_tables.sort(key=lambda t: getattr(t["zakazka"], "zakazka_cislo", "") or "")

    return render(request, "statistiky.html", {
        "scope": scope,
        "ym": ym_for_template,
        "y": y_for_template,
        "prev_ym": prev_ym, "next_ym": next_ym,
        "prev_y": prev_y,   "next_y": next_y,

        "first_day": first_day,
        "last_day": last_day,
        "calc_until": calc_until,

        "employees_rows": employees_rows,
        "employees_total": employees_total,

        "externist_rows": externist_rows,
        "externists_total": externists_total,

        "new_projects": new_projects,
        "closed_projects": closed_projects,

        # nové tabulky po zakázkách v aktuálním období
        "projects_month_tables": month_tables,
    })





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

def _q2(x: Decimal | None) -> Decimal | None:
    if x is None:
        return None
    return Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def _as_dec(val, default="0"):
    try:
        return Decimal(str(val))
    except Exception:
        return Decimal(default)

def _project_finance_for(zakazka) -> dict | None:
    """
    Přehled financí pro off-canvas:
      - Předpoklad: predp_cas * sazba  vs. predp_cas * orientacni_hodinove_naklady (Kč/h)
      - Skutečnost:
          hrubý výnos = (sjednaná_cena – subdodávky Arched),
          náklady = Σ hodiny * (efektivní_sazba_hod_daného_měsíce + firemní_overhead/overhead_divisor + rezie_hod)
                    + cestovné
      - Rozpad dle osob (náklad/hod = (mzda + režie)/hod)
    """
    if not zakazka:
        return None

    ZERO = Decimal("0")

    # --- lokální helpery ------------------------------------------------------
    def _q2(x: Decimal | None) -> Decimal | None:
        if x is None:
            return None
        return Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def _as_dec(val, default="0"):
        try:
            return Decimal(str(val))
        except Exception:
            return Decimal(default)

    def _month_bounds(y: int, m: int) -> tuple[dt.date, dt.date]:
        last = calendar.monthrange(y, m)[1]
        return (dt.date(y, m, 1), dt.date(y, m, last))

    # efektivní hodinovka zaměstnance pro konkrétní měsíc (cache)
    _rate_cache: dict[tuple[int, int, int], Decimal] = {}  # (emp_id, year, month) -> rate

    def _effective_rate_for_month(emp, year: int, month: int) -> Decimal:
        """
        Hodinovka pro (year, month):
          1) když emp.sazba_hod > 0 → použij,
          2) jinak (měsíční mzda) / (plánované hodiny v měsíci).
        """
        key = (emp.id, year, month)
        if key in _rate_cache:
            return _rate_cache[key]

        base = _as_dec(getattr(emp, "sazba_hod", 0), "0")
        if base > ZERO:
            rate = base.quantize(Decimal("0.01"))
            _rate_cache[key] = rate
            return rate

        first_day, last_day = _month_bounds(year, month)
        plan_h = planned_hours(emp, first_day, last_day) or ZERO
        if plan_h <= ZERO:
            _rate_cache[key] = ZERO
            return ZERO

        monthly_fields = ("mzda_mesic", "mesicni_mzda", "mzda", "plat_mesic", "salary_monthly")
        monthly_wage = None
        for f in monthly_fields:
            if hasattr(emp, f):
                val = getattr(emp, f)
                if val is not None:
                    v = _as_dec(val, None)
                    if v is not None and v > ZERO:
                        monthly_wage = v
                        break

        if monthly_wage is None:
            _rate_cache[key] = ZERO
            return ZERO

        rate = (monthly_wage / plan_h).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        _rate_cache[key] = rate
        return rate

    # --- PŘEDPOKLAD -----------------------------------------------------------
    predp_cas = _as_dec(getattr(zakazka, "predpokladany_cas", 0), "0")

    sazba = None
    if getattr(zakazka, "sazba_id", None):
        sazba = _as_dec(getattr(zakazka.sazba, "hodnota", None), None)

    orient_nakl_hod = None
    if getattr(zakazka, "orientacni_hodinove_naklady", None) is not None:
        orient_nakl_hod = _as_dec(getattr(zakazka, "orientacni_hodinove_naklady"), None)

    predp_vynos = predp_naklad = predp_zisk = None
    if sazba is not None:
        predp_vynos = predp_cas * sazba
    if orient_nakl_hod is not None:
        predp_naklad = predp_cas * orient_nakl_hod
    if predp_vynos is not None and predp_naklad is not None:
        predp_zisk = predp_vynos - predp_naklad

    # --- SKUTEČNOST -----------------------------------------------------------
    # sjednaná cena: explicitně z pole, jinak sazba * PŘEDPOKLÁDANÉ hodiny
    sjednana_cena = None
    if getattr(zakazka, "sjednana_cena", None) is not None:
        sjednana_cena = _as_dec(zakazka.sjednana_cena, None)
    elif sazba is not None and predp_cas and predp_cas > ZERO:
        sjednana_cena = (sazba * predp_cas).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    logs = (
        ZakazkaZamestnanec.objects
        .filter(zakazka=zakazka)
        .select_related("zamestnanec")
        .order_by("den_prace")
    )

    hours_by_emp: dict[int, Decimal] = defaultdict(lambda: ZERO)

    wages_sum    = ZERO  # mzdy (efektivní hodinovka * h)
    overhead_sum = ZERO  # firemní overhead/÷ + osobní režie (rezie_hod)
    cestovne_sum = ZERO

    per_emp_tmp: dict[int, dict] = {}

    for v in logs:
        h = _as_dec(_hours_between(v.den_prace, v.cas_od, v.cas_do), "0")
        if h <= ZERO:
            continue

        emp = v.zamestnanec
        y, m = v.den_prace.year, v.den_prace.month

        # efektivní hodinovka dle měsíce
        rate_h = _effective_rate_for_month(emp, y, m)

        # cestovné
        km = _as_dec(getattr(v, "najete_km", 0), "0")
        rate_km = _as_dec(getattr(emp, "sazba_km", 0), "0")

        # firemní režie dle dne výkazu, dělená dělitelem; + osobní režie/hod
        divisor = _as_dec(getattr(emp, "overhead_divisor", 1) or 1, "1")
        if divisor <= ZERO:
            divisor = Decimal("1")
        try:
            oh_raw = overhead_rate_on(v.den_prace)  # Kč/h (Decimal)
            oh_part = _as_dec(oh_raw, "0") / divisor
        except Exception:
            oh_part = ZERO
        emp_oh = _as_dec(getattr(emp, "rezie_hod", 0) or 0, "0")  # osobní režie / hod

        # kumulace souhrnů
        hours_by_emp[emp.id] += h
        wages_sum    += h * rate_h
        overhead_sum += h * (oh_part + emp_oh)
        cestovne_sum += km * rate_km

        # per-employee agregace do off-canvas tabulky
        agg = per_emp_tmp.get(emp.id)
        if not agg:
            agg = {
                "emp": f"{getattr(emp, 'jmeno', '')} {getattr(emp, 'prijmeni', '')}".strip() or getattr(emp, 'username', '—'),
                "hod": ZERO,
                "cestovne": ZERO,
                "wages": ZERO,
                "over": ZERO,
            }
            per_emp_tmp[emp.id] = agg

        agg["hod"]      += h
        agg["cestovne"] += km * rate_km
        agg["wages"]    += h * rate_h
        agg["over"]     += h * (oh_part + emp_oh)

    skut_hodin = sum(hours_by_emp.values(), ZERO)

    # subdodávky fakturované Arched
    subdodavky_arched = ZakazkaSubdodavka.objects.filter(
        zakazka=zakazka, fakturuje_arched=True
    ).aggregate(s=Sum("cena"))["s"] or ZERO

    hruby_vynos = None
    if sjednana_cena is not None:
        hruby_vynos = sjednana_cena - _as_dec(subdodavky_arched, "0")

    skut_hod_sazba = None
    if hruby_vynos is not None and skut_hodin > ZERO:
        skut_hod_sazba = hruby_vynos / skut_hodin

    # per-employee tabulka pro off-canvas
    per_emp = []
    for agg in per_emp_tmp.values():
        if agg["hod"] > ZERO or agg["cestovne"] > ZERO:
            naklad_hod = (agg["wages"] + agg["over"]) / (agg["hod"] or Decimal("1"))
            celkem = agg["wages"] + agg["over"] + agg["cestovne"]
            per_emp.append({
                "emp": agg["emp"],
                "hod": _q2(agg["hod"]),
                "cestovne": _q2(agg["cestovne"]),
                "naklad_hod": _q2(naklad_hod),
                "celkem": _q2(celkem),
            })

    naklady_prace_celkem = wages_sum
    rezie_celkem = overhead_sum                      # firemní + osobní režie
    naklady_celkem = wages_sum + overhead_sum + cestovne_sum

    skut_zisk = None
    if hruby_vynos is not None:
        skut_zisk = hruby_vynos - naklady_celkem

    return {
        # Předpoklad
        "predp_cas": _q2(predp_cas),
        "sazba": _q2(sazba),
        "predp_vynos": _q2(predp_vynos),
        "orient_nakl_hod": _q2(orient_nakl_hod),
        "predp_naklad": _q2(predp_naklad),
        "predp_zisk": _q2(predp_zisk),

        # Skutečnost
        "sjednana_cena": _q2(sjednana_cena),
        "subdodavky_arched": _q2(subdodavky_arched),
        "hruby_vynos": _q2(hruby_vynos),

        "skut_hodin": _q2(skut_hodin),
        "skut_hod_sazba": _q2(skut_hod_sazba),

        "cestovne_celkem": _q2(cestovne_sum),
        "naklady_prace_celkem": _q2(naklady_prace_celkem),
        "rezie_celkem": _q2(rezie_celkem),           # = firemní OH/÷ + rezie_hod
        "naklady_celkem": _q2(naklady_celkem),

        "skut_zisk": _q2(skut_zisk),

        "per_emp": per_emp,
    }
