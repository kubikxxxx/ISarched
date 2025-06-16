# views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import HttpResponseForbidden
from django.utils import timezone
from datetime import datetime, timedelta
from django.utils.timezone import now
from django.db.models import Sum
from .forms import LoginForm, ZakazkaForm, EmployeeForm, ClientForm, KlientPoznamkaForm, SubdodavkaForm, \
    SubdodavatelForm, UredniZapisForm, VykazForm, RozsahPraceFormSet, ZamestnanecZakazkaForm
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
            prirazeni__datum_prideleni__lte=now()
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
        vykazy = zakazka_detail.zakazkazamestnanec_set \
            .select_related('zamestnanec') \
            .order_by('-den_prace')
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

    if zakazka_detail:
        vykazy_qs = zakazka_detail.zakazkazamestnanec_set.all()
        for vykaz in vykazy_qs:
            if vykaz.cas_od and vykaz.cas_do:
                dt_od = datetime.combine(datetime.today(), vykaz.cas_od)
                dt_do = datetime.combine(datetime.today(), vykaz.cas_do)
                rozdil = dt_do - dt_od
                odpracovano_hodin += rozdil.total_seconds() / 3600

        predpokladany_cas = zakazka_detail.predpokladany_cas or 0
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

    return render(request, 'homepage.html', {
        'zakazky': zakazky.order_by('-id'),
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
        'odpracovano_hodin': round(odpracovano_hodin, 1),
        'zbyva_hodin': round(zbyva_hodin, 1),
        'barva_zbyva': barva_zbyva,
        'progress_percent': progress_percent,
        'predpokladany_cas': zakazka_detail.predpokladany_cas if zakazka_detail else 0,
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
        'is_edit': 'True'
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

    if request.method == 'POST':
        ZakazkaSubdodavka.objects.filter(zakazka=zakazka).delete()

        for sub_id in request.POST.getlist('subdodavka'):
            subdodavka = Subdodavka.objects.get(id=sub_id)

            subdodavatel_id = request.POST.get(f'subdodavatel_{sub_id}')
            subdodavatel = Subdodavatel.objects.filter(id=subdodavatel_id).first() if subdodavatel_id else None

            # Čtení hodnoty ceny a navýšení – s převodem z textu na číslo
            cena_raw = request.POST.get(f'cena_{sub_id}', '0')
            navyseni_raw = request.POST.get(f'navyseni_{sub_id}', '0')

            try:
                cena = float(cena_raw.replace(',', '.'))
            except ValueError:
                cena = 0

            try:
                navyseni = float(navyseni_raw.replace(',', '.'))
            except ValueError:
                navyseni = 0

            fakturuje = request.POST.get(f'fakturace_{sub_id}', '')

            ZakazkaSubdodavka.objects.create(
                zakazka=zakazka,
                subdodavka=subdodavka,
                subdodavatel=subdodavatel,
                cena=cena,
                navyseni=navyseni,
                fakturuje_klientovi=(fakturuje == 'klient'),
                fakturuje_arched=(fakturuje == 'arched'),
            )

        return redirect(f'/homepage/?detail_zakazka={zakazka_id}')

    assigned = ZakazkaSubdodavka.objects.filter(zakazka=zakazka)
    return render(request, 'zakazka_subdodavky_form.html', {
        'zakazka': zakazka,
        'subdodavky': subdodavky,
        'subdodavatele': subdodavatele,
        'assigned': assigned,
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
    if not request.user.is_admin:
        return HttpResponseForbidden("Pouze admin může přidávat klienty.")

    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            klient = form.save()
            text = form.cleaned_data.get('poznamka')
            if text:
                KlientPoznamka.objects.create(klient=klient, text=text, datum=timezone.now())
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
            return redirect(f'/homepage/?detail_zamestnanci={zakazka_id}')
    else:
        form = ZamestnanecZakazkaForm()

    return render(request, 'prirazeni_form.html', {
        'form': form,
        'zakazka': zakazka
    })


@login_required
def upravit_prirazeni_view(request, prirazeni_id):
    if not request.user.is_admin:
        return HttpResponseForbidden("Pouze admin může upravovat přiřazení.")

    prirazeni = get_object_or_404(ZamestnanecZakazka, id=prirazeni_id)
    if request.method == 'POST':
        prirazeni.prideleno_hodin = request.POST.get('hodiny')
        prirazeni.premie_predpoklad = request.POST.get('premie_predpoklad') or None
        prirazeni.premie_skutecnost = request.POST.get('premie_skutecnost') or None
        prirazeni.datum_prideleni = request.POST.get('datum_prideleni') or timezone.now()
        prirazeni.popis = request.POST.get('popis')
        prirazeni.save()
        return redirect(f'/homepage/?detail_zamestnanci={prirazeni.zakazka.id}')

    return render(request, 'upravit_prirazeni_form.html', {
        'prirazeni': prirazeni
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
