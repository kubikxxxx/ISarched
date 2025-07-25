from cProfile import label
from datetime import datetime
from email.policy import default

from django import forms
from django.forms import DateInput, Textarea
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.auth.forms import UserCreationForm
from django.utils.timezone import now
from django.forms import modelformset_factory
from .models import Zakazka, Zamestnanec, Klient, Sazba, KlientPoznamka, Subdodavka, Subdodavatel, UredniZapis, \
    ZakazkaZamestnanec, RozsahPrace, RozsahText, ZamestnanecZakazka


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
    termin = forms.DateTimeField(
        label='Termín',
        widget=forms.DateInput(attrs={'type': 'date'})
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

    class Meta:
        model = Zakazka
        exclude = ['sazba', 'zakazka_konec_skut']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        try:
            latest = Sazba.objects.latest('sazba_start')
            self.fields['sazba_hodnota'].initial = latest.hodnota
        except Sazba.DoesNotExist:
            self.fields['sazba_hodnota'].initial = 0

        # ⬇️ Tohle doplní YYYY-MM-DD do input[type=date] polí při editaci
        for field_name in ['termin', 'zakazka_start', 'zakazka_konec_predp']:
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

    def save(self, commit=True):
        zakazka = super().save(commit=False)
        sazba = Sazba.objects.create(
            hodnota=self.cleaned_data['sazba_hodnota'],
            sazba_start=now()
        )
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
    sazba_hod = forms.IntegerField(label='Hodinová sazba', min_value=0)

    class Meta:
        model = Zamestnanec
        fields = ('username', 'jmeno', 'prijmeni', 'titul', 'is_admin', 'sazba_hod')


class ClientForm(forms.ModelForm):
    class Meta:
        model = Klient
        fields = '__all__'
        labels = {
            'nazev': 'Jméno klienta',
            'dic': 'DIČ',
            'sidlo_mesto': 'Město sídla',
            'sidlo_ulice': 'Ulice sídla',
            'sidlo_psc': 'PSČ sídla',
            'ico': 'IČO',
            'email': 'E-mail',
            'telefon': 'Telefon',
            'fakturacni_nazev': 'Fakturační název',
            'fakturacni_mesto': 'Fakturační město',
            'fakturacni_ulice': 'Fakturační ulice',
            'fakturacni_psc': 'Fakturační PSČ',
            'fakturacni_ico': 'Fakturační IČO',
            'fakturacni_email': 'Fakturační e-mail',
            'fakturacni_telefon': 'Fakturační telefon',
        }
        widgets = {
            'nazev': forms.TextInput(attrs={'class': 'form-control'}),
            'dic': forms.TextInput(attrs={'class': 'form-control'}),
            'ico': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'telefon': forms.TextInput(attrs={'class': 'form-control'}),
            'sidlo_mesto': forms.TextInput(attrs={'class': 'form-control'}),
            'sidlo_ulice': forms.TextInput(attrs={'class': 'form-control'}),
            'sidlo_psc': forms.TextInput(attrs={'class': 'form-control'}),
            'fakturacni_nazev': forms.TextInput(attrs={'class': 'form-control'}),
            'fakturacni_mesto': forms.TextInput(attrs={'class': 'form-control'}),
            'fakturacni_ulice': forms.TextInput(attrs={'class': 'form-control'}),
            'fakturacni_psc': forms.TextInput(attrs={'class': 'form-control'}),
            'fakturacni_ico': forms.TextInput(attrs={'class': 'form-control'}),
            'fakturacni_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'fakturacni_telefon': forms.TextInput(attrs={'class': 'form-control'}),
        }


class KlientPoznamkaForm(forms.ModelForm):
    class Meta:
        model = KlientPoznamka
        fields = ['text']


class SubdodavkaForm(forms.ModelForm):
    nazev = forms.CharField(label='Název', max_length=50)

    class Meta:
        model = Subdodavka
        fields = ['nazev']


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
        widgets = {
            'titul_pred': forms.TextInput(attrs={'class': 'form-control'}),
            'jmeno': forms.TextInput(attrs={'class': 'form-control'}),
            'prijmeni': forms.TextInput(attrs={'class': 'form-control'}),
            'titul_za': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'telefon': forms.TextInput(attrs={'class': 'form-control'}),
            'ico': forms.TextInput(attrs={'class': 'form-control'}),
            'dic': forms.TextInput(attrs={'class': 'form-control'}),
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


class VykazForm(forms.ModelForm):
    den_prace = forms.DateField(
        label='Den práce',
        widget=forms.DateInput(attrs={'type': 'date'}),
        initial=now().date  # <- výchozí hodnota dnešní datum
    )
    cas_od = forms.TimeField(
        label='Čas od',
        required=False,
        widget=forms.TimeInput(attrs={'type': 'time'})
    )
    cas_do = forms.TimeField(
        label='Čas do',
        required=False,
        widget=forms.TimeInput(attrs={'type': 'time'})
    )
    popis = forms.CharField(label='Popis', required=False)
    najete_km = forms.DecimalField(label='Najeté km', required=False)

    class Meta:
        model = ZakazkaZamestnanec
        fields = ['den_prace', 'cas_od', 'cas_do', 'popis', 'najete_km']


class RozsahPraceForm(forms.ModelForm):
    novy_text = forms.CharField(
        label='',
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Nový rozsah práce'})
    )

    text = forms.ModelChoiceField(
        queryset=RozsahText.objects.all(),
        required=False,  # ⬅️ toto přidej!
        widget=forms.Select(attrs={
            'class': 'form-select',
            'style': 'width: 45%; display: inline-block; margin-right: 10px;'
        })
    )

    class Meta:
        model = RozsahPrace
        fields = ['text', 'novy_text']

    def clean(self):
        cleaned_data = super().clean()
        novy_text = cleaned_data.get('novy_text', '').strip()
        text = cleaned_data.get('text')

        # Pokud není vyplněno vůbec nic, považuj řádek za prázdný a ignoruj ho
        if not text and not novy_text:
            if self.empty_permitted:
                raise forms.ValidationError("Prázdný řádek – nebude uložen.")
            return cleaned_data

        # Pokud je vyplněn nový text, vytvoříme nový RozsahText
        if novy_text:
            text_obj, _ = RozsahText.objects.get_or_create(text=novy_text)
            cleaned_data['text'] = text_obj

        return cleaned_data


class ZamestnanecZakazkaForm(forms.ModelForm):
    zamestnanec = forms.ModelChoiceField(
        queryset=Zamestnanec.objects.all(),
        label='Zaměstnanec',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = ZamestnanecZakazka
        fields = ['zamestnanec', 'prideleno_hodin', 'premie_predpoklad', 'premie_skutecnost', 'datum_prideleni',
                  'popis']
        widgets = {
            'prideleno_hodin': forms.NumberInput(attrs={'class': 'form-control'}),
            'premie_predpoklad': forms.NumberInput(attrs={'class': 'form-control'}),
            'premie_skutecnost': forms.NumberInput(attrs={'class': 'form-control'}),
            'datum_prideleni': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'popis': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class CustomPasswordChangeForm(PasswordChangeForm):
    old_password = forms.CharField(
        label="Staré heslo",
        strip=False,
        widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "current-password"}),
    )
    new_password1 = forms.CharField(
        label="Nové heslo",
        widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "new-password"}),
        strip=False,
        help_text=None,
    )
    new_password2 = forms.CharField(
        label="Potvrzení nového hesla",
        strip=False,
        widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "new-password"}),
    )

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


RozsahPraceFormSet = modelformset_factory(
    RozsahPrace,
    form=RozsahPraceForm,
    fields=['id', 'text', 'novy_text'],
    extra=1,
    can_delete=True
)