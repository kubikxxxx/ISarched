from datetime import datetime

from django import forms
from django.forms import DateInput, Textarea, TimeInput
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, UserCreationForm
from django.utils.timezone import now
from django.forms import modelformset_factory
from django.utils.timezone import localtime

from .models import (
    Zakazka, Zamestnanec, Klient, Sazba, KlientPoznamka,
    Subdodavka, Subdodavatel, UredniZapis, ZakazkaZamestnanec,
    RozsahPrace, RozsahText, ZamestnanecZakazka
)


class LoginForm(AuthenticationForm):
    username = forms.CharField(label='Uživatelské jméno')
    password = forms.CharField(widget=forms.PasswordInput, label='Heslo')


class ZakazkaForm(forms.ModelForm):
    sazba_hodnota = forms.DecimalField(label='Sazba (Kč/hod)', max_digits=18, decimal_places=2)

    hip = forms.ModelChoiceField(
        queryset=Zamestnanec.objects.all(),
        required=False,
        label="HIP"
    )
    zakazka_konec_skut = forms.DateTimeField(
        label='Skutečný konec (vyplněním se ukončí zakázka)',
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=False
    )

    zakazka_start = forms.DateTimeField(
        label='Začátek zakázky',
        required=False,
        initial=now,
        widget=forms.DateInput(attrs={'type': 'date'})
    )

    zakazka_konec_predp = forms.DateTimeField(
        label='Předpokládaný konec',
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )

    nazev = forms.CharField(
        label='Název',
        max_length=50
    )

    popis_zadani = forms.CharField(
        label='Zadání',
        widget=Textarea(attrs={'rows': 3})
    )

    zakazka_cislo = forms.CharField(label='Číslo zakázky', max_length=50)

    predpokladany_cas = forms.IntegerField(label='Předpokládaný čas (h)', min_value=0)

    misto_stavby = forms.CharField(
        label='Místo stavby',
        widget=Textarea(attrs={'rows': 2}),
        strip=True
    )

    plna_moc = forms.BooleanField(label='Plná moc', required=False)

    orientacni_naklady = forms.IntegerField(label='Orientační náklady')

    class Meta:
        model = Zakazka
        exclude = ['sazba', 'termin']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        try:
            latest = Sazba.objects.latest('sazba_start')
            self.fields['sazba_hodnota'].initial = latest.hodnota
        except Sazba.DoesNotExist:
            self.fields['sazba_hodnota'].initial = 0

        for field_name in ['termin', 'zakazka_start', 'zakazka_konec_predp', 'zakazka_konec_skut']:
            value = getattr(self.instance, field_name, None)
            if value:
                self.initial[field_name] = value.strftime('%Y-%m-%d')

    def clean_termin(self):
        datum = self.cleaned_data.get('termin')
        if datum and isinstance(datum, datetime):
            return datum.replace(hour=0, minute=0, second=0, microsecond=0)
        return datum

    def clean_zakazka_start(self):
        datum = self.cleaned_data.get('zakazka_start')
        if datum and isinstance(datum, datetime):
            return datum.replace(hour=0, minute=0, second=0, microsecond=0)
        return datum

    def clean_zakazka_konec_predp(self):
        datum = self.cleaned_data.get('zakazka_konec_predp')
        if datum and isinstance(datum, datetime):
            return datum.replace(hour=0, minute=0, second=0, microsecond=0)
        return datum

    def clean_zakazka_konec_skut(self):
        datum = self.cleaned_data.get('zakazka_konec_skut')
        if datum and isinstance(datum, datetime):
            return datum.replace(hour=0, minute=0, second=0, microsecond=0)
        return datum

    def save(self, commit=True):
        zakazka = super().save(commit=False)
        sazba = Sazba.objects.create(hodnota=self.cleaned_data['sazba_hodnota'], sazba_start=now())
        zakazka.sazba = sazba
        if commit:
            zakazka.save()
        return zakazka


class EmployeeForm(UserCreationForm):
    username = forms.CharField(label='Uživatelské jméno (přihlašovací)')
    jmeno = forms.CharField(label='Jméno', max_length=255)
    prijmeni = forms.CharField(label='Příjmení', max_length=255)
    titul = forms.CharField(label='Titul', max_length=255, required=False)
    is_admin = forms.BooleanField(label='Administrátor', required=False)
    sazba_hod = forms.IntegerField(label='Hodinová sazba', min_value=0, localize=True)

    class Meta:
        model = Zamestnanec
        fields = ('username', 'jmeno', 'prijmeni', 'titul', 'is_admin', 'sazba_hod')


class EmployeeEditForm(forms.ModelForm):
    class Meta:
        model = Zamestnanec
        fields = ('username', 'jmeno', 'prijmeni', 'titul', 'is_admin', 'sazba_hod')
        labels = {
            'username': 'Uživatelské jméno (přihlašovací)',
            'jmeno': 'Jméno',
            'prijmeni': 'Příjmení',
            'titul': 'Titul',
            'is_admin': 'Administrátor',
            'sazba_hod': 'Hodinová sazba',
        }
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'jmeno': forms.TextInput(attrs={'class': 'form-control'}),
            'prijmeni': forms.TextInput(attrs={'class': 'form-control'}),
            'titul': forms.TextInput(attrs={'class': 'form-control'}),
            'sazba_hod': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_admin': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ClientForm(forms.ModelForm):
    ico = forms.CharField(required=False, label='IČO')
    dic = forms.CharField(required=False, label='DIČ')
    fakturacni_ico = forms.CharField(required=False, label='Fakturační IČO')

    class Meta:
        model = Klient
        fields = '__all__'
        labels = {
            'nazev': 'Název firmy',
            'email': 'E-mail',
            'telefon': 'Telefon',
            'sidlo_mesto': 'Město sídla',
            'sidlo_ulice': 'Ulice sídla',
            'sidlo_psc': 'PSČ sídla',
            'fakturacni_nazev': 'Fakturační název',
            'fakturacni_mesto': 'Fakturační město',
            'fakturacni_ulice': 'Fakturační ulice',
            'fakturacni_psc': 'Fakturační PSČ',
            'fakturacni_ico': 'Fakturační IČO',
            'fakturacni_email': 'Fakturační e-mail',
            'fakturacni_telefon': 'Fakturační telefon',
        }


class KlientPoznamkaForm(forms.ModelForm):
    class Meta:
        model = KlientPoznamka
        fields = ['text']
        labels = {
            'text': 'Poznámka',
        }


class SubdodavkaForm(forms.ModelForm):
    class Meta:
        model = Subdodavka
        fields = ['nazev']
        labels = {
            'nazev': 'Název subdodávky',
        }


class SubdodavatelForm(forms.ModelForm):
    class Meta:
        model = Subdodavatel
        fields = ['titul_pred', 'jmeno', 'prijmeni', 'titul_za', 'email', 'telefon', 'ico', 'dic']
        labels = {
            'titul_pred': 'Titul před',
            'jmeno': 'Jméno',
            'prijmeni': 'Příjmení',
            'titul_za': 'Titul za',
            'email': 'E-mail',
            'telefon': 'Telefon',
            'ico': 'IČO',
            'dic': 'DIČ',
        }


class UredniZapisForm(forms.ModelForm):
    datum = forms.DateTimeField(
        label='Datum vystavení',
        widget=forms.DateTimeInput(attrs={'type': 'date'})
    )
    termin_do = forms.DateTimeField(
        label='Termín do',
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'date'})
    )

    class Meta:
        model = UredniZapis
        fields = ['popis', 'datum', 'termin_do']
        labels = {
            'popis': 'Popis',
            'datum': 'Datum vystavení',
            'termin_do': 'Termín do',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field_name in ['datum', 'termin_do']:
            value = getattr(self.instance, field_name, None)
            if value and isinstance(value, datetime):
                local_value = localtime(value)  # správné převedení na lokální čas
                self.initial[field_name] = local_value.strftime('%Y-%m-%d')


class VykazForm(forms.ModelForm):
    den_prace = forms.DateField(
        label='Den práce',
        widget=forms.DateInput(attrs={'type': 'date'}),
        input_formats=['%Y-%m-%d']
    )
    cas_od = forms.TimeField(
        label='Čas od',
        required=False,
        widget=forms.TimeInput(attrs={'type': 'time'}),
        input_formats=['%H:%M']
    )
    cas_do = forms.TimeField(
        label='Čas do',
        required=False,
        widget=forms.TimeInput(attrs={'type': 'time'}),
        input_formats=['%H:%M']
    )
    popis = forms.CharField(label='Popis', required=False)
    najete_km = forms.DecimalField(label='Najeté km', required=False, localize=True)

    class Meta:
        model = ZakazkaZamestnanec
        fields = ['den_prace', 'cas_od', 'cas_do', 'popis', 'najete_km']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.initial['den_prace'] = self.instance.den_prace.strftime('%Y-%m-%d') if self.instance.den_prace else ''
            self.initial['cas_od'] = self.instance.cas_od.strftime('%H:%M') if self.instance.cas_od else ''
            self.initial['cas_do'] = self.instance.cas_do.strftime('%H:%M') if self.instance.cas_do else ''

class RozsahPraceForm(forms.ModelForm):
    novy_text = forms.CharField(
        label='Nový rozsah práce',
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Zadejte nový rozsah práce', 'class': 'form-control'})
    )

    class Meta:
        model = RozsahPrace
        fields = ['text', 'novy_text']
        labels = {
            'text': 'Výběr rozsahu práce',
        }
        widgets = {
            'text': forms.Select(attrs={'class': 'form-select'}),
        }

class ZamestnanecZakazkaForm(forms.ModelForm):
    premie_predpoklad = forms.DecimalField(required=False, localize=True, label='Předpokládaná prémie')
    premie_skutecnost = forms.DecimalField(required=False, localize=True, label='Skutečná prémie')
    prideleno_hodin = forms.IntegerField(localize=True, label='Přiděleno hodin')

    class Meta:
        model = ZamestnanecZakazka
        fields = ['zamestnanec', 'prideleno_hodin', 'premie_predpoklad', 'premie_skutecnost', 'datum_prideleni', 'popis']
        labels = {
            'zamestnanec': 'Zaměstnanec',
            'datum_prideleni': 'Datum přidělení',
            'popis': 'Popis',
        }


class CustomPasswordChangeForm(PasswordChangeForm):
    old_password = forms.CharField(label="Staré heslo", strip=False, widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "current-password"}))
    new_password1 = forms.CharField(label="Nové heslo", widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "new-password"}), strip=False, help_text=None)
    new_password2 = forms.CharField(label="Potvrzení nového hesla", strip=False, widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "new-password"}))


RozsahPraceFormSet = modelformset_factory(
    RozsahPrace,
    form=RozsahPraceForm,
    fields=['text', 'novy_text'],
    extra=1,
    can_delete=True
)
