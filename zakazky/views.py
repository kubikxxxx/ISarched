# views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib.auth.forms import PasswordChangeForm
from django.http import HttpResponseForbidden
from django.contrib.auth import update_session_auth_hash
from django.utils import timezone
from datetime import datetime, timedelta
from django.contrib import messages
from django.utils.timezone import now
from django.db.models import Sum
from simple_history.utils import update_change_reason
from simple_history.models import HistoricalRecords
from simple_history.utils import get_history_model_for_model
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .models import UredniZapis
from .forms import LoginForm, ZakazkaForm, EmployeeForm, ClientForm, KlientPoznamkaForm, SubdodavkaForm, \
    SubdodavatelForm, UredniZapisForm, VykazForm, RozsahPraceFormSet, ZamestnanecZakazkaForm, CustomPasswordChangeForm, \
    EmployeeEditForm
from .models import Zakazka, Zamestnanec, Klient, KlientPoznamka, Subdodavka, Subdodavatel, ZakazkaSubdodavka, \
    UredniZapis, ZakazkaZamestnanec, ZamestnanecZakazka, RozsahPrace


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
    historie_urednich_zaznamu = None
    if zakazka_detail:
        uredni_ids = UredniZapis.objects.filter(zakazka=zakazka_detail).values_list('id', flat=True)
        historie_urednich_zaznamu = get_history_model_for_model(UredniZapis).objects.filter(id__in=uredni_ids).order_by(
            '-history_date')
    prirazeni_vypocty = []
    if zamestnanci_prirazeni:
        for prirazeni in zamestnanci_prirazeni:
            prideleno = prirazeni.prideleno_hodin or 0
            odpracovano = 0
            vykazy = ZakazkaZamestnanec.objects.filter(
                zakazka=zakazka_zam,
                zamestnanec=prirazeni.zamestnanec
            )
            for v in vykazy:
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

            vidi = prirazeni.datum_prideleni and prirazeni.datum_prideleni <= now() and not prirazeni.skryta
            datum_ok = prirazeni.datum_prideleni and prirazeni.datum_prideleni <= now()
            prirazeni_vypocty.append({
                'prirazeni': prirazeni,
                'prideleno': prideleno,
                'odpracovano': round(odpracovano, 1),
                'zbyva': round(zbyva, 1),
                'barva': barva,
                'skryta': prirazeni.skryta,
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
        'prirazeni_vypocty': prirazeni_vypocty,
    })


@login_required
def create_zakazka_view(request):
    if not request.user.is_admin:
        return HttpResponseForbidden("Pouze administrátor může vytvářet zakázky.")

    if request.method == 'POST':
        form = ZakazkaForm(request.POST)
        formset = RozsahPraceFormSet(request.POST, queryset=RozsahPrace.objects.none())  # ⬅️ tady

        if form.is_valid() and formset.is_valid():
            zakazka = form.save()
            for subform in formset:
                if subform.cleaned_data and not subform.cleaned_data.get('DELETE', False):
                    rozsah = subform.save(commit=False)
                    rozsah.zakazka = zakazka
                    rozsah.vytvoril = request.user
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
        'is_edit': 'False'
    })


@login_required
def edit_zakazka_view(request, zakazka_id):
    if not request.user.is_admin:
        return HttpResponseForbidden("Pouze administrátor může upravovat zakázky.")

    zakazka = get_object_or_404(Zakazka, id=zakazka_id)

    if request.method == 'POST':
        form = ZakazkaForm(request.POST, instance=zakazka)
        formset = RozsahPraceFormSet(request.POST, queryset=RozsahPrace.objects.filter(zakazka=zakazka))

        if form.is_valid() and formset.is_valid():
            form.save()

            for subform in formset:
                if subform.cleaned_data:
                    if subform.cleaned_data.get('DELETE', False):
                        if subform.instance.pk:
                            subform.instance.delete()
                    else:
                        rozsah = subform.save(commit=False)
                        rozsah.zakazka = zakazka
                        if not rozsah.vytvoril:
                            rozsah.vytvoril = request.user
                        rozsah.save()

            return redirect(f'/homepage/?detail_zakazka={zakazka_id}')
        else:
            print("Form errors:", form.errors)
            print("Formset errors:", formset.errors)
    else:
        form = ZakazkaForm(instance=zakazka)
        formset = RozsahPraceFormSet(queryset=RozsahPrace.objects.filter(zakazka=zakazka))

    return render(request, 'zakazka_form.html', {
        'form': form,
        'formset': formset,
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
            cena = request.POST.get(f"cena_{sub_id}")
            navyseni = request.POST.get(f"navyseni_{sub_id}")
            fakturace = request.POST.get(f"fakturace_{sub_id}")

            # ✅ Validace
            if not subdodavatel_id or not cena or not navyseni or not fakturace:
                messages.error(request, f"Chybí údaje pro subdodávku ID {sub_id}. Všechna pole musí být vyplněna.")
                return redirect(request.path)

            ZakazkaSubdodavka.objects.create(
                zakazka=zakazka,
                subdodavka_id=sub_id,
                subdodavatel_id=subdodavatel_id,
                cena=cena,
                navyseni=navyseni,
                fakturuje_klientovi=(fakturace == "klient"),
                fakturuje_arched=(fakturace == "arched"),
            )

        messages.success(request, "Subdodávky byly uloženy.")
        return redirect("homepage")  # nebo přesměrování zpět na detail zakázky

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

    if not request.user.is_admin and not ZamestnanecZakazka.objects.filter(zakazka=zakazka,
                                                                           zamestnanec=request.user).exists():
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
        form = VykazForm(initial={'den_prace': now().date()})  # ⬅️ zde se předvyplňuje dnešek

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