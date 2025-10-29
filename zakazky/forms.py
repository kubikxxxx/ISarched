from datetime import datetime, date, timedelta
import calendar
from decimal import Decimal
from django import forms
from django.forms import DateInput, Textarea, TimeInput
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, UserCreationForm
from django.utils.timezone import now, localdate
from django.forms import modelformset_factory
from django.utils.timezone import localtime

from .models import (
    Zakazka, Zamestnanec, Klient, Sazba, KlientPoznamka,
    Subdodavka, Subdodavatel, UredniZapis, ZakazkaZamestnanec,
    RozsahPrace, RozsahText, ZamestnanecZakazka, OverheadRate
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
    nazev = forms.CharField(label='Název', max_length=50)
    popis_zadani = forms.CharField(label='Zadání', widget=Textarea(attrs={'rows': 3}))
    zakazka_cislo = forms.CharField(label='Číslo zakázky', max_length=50)
    predpokladany_cas = forms.IntegerField(label='Předpokládaný čas (h)', min_value=0)
    misto_stavby = forms.CharField(label='Místo stavby', widget=Textarea(attrs={'rows': 2}), strip=True)
    plna_moc = forms.BooleanField(label='Plná moc', required=False)
    orientacni_naklady = forms.IntegerField(label='Rozpočet na stavbu')
    sjednana_cena = forms.DecimalField(
        label='Sjednaná cena (Kč)',
        max_digits=18, decimal_places=2, min_value=0, required=False
    )
    zaloha = forms.DecimalField(
        label='Záloha (Kč)',
        max_digits=18, decimal_places=2, min_value=0, required=False
    )

    class Meta:
        model = Zakazka
        exclude = ['sazba', 'termin']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk and getattr(self.instance, "sazba_id", None):
            self.fields['sazba_hodnota'].initial = self.instance.sazba.hodnota
        else:
            latest = Sazba.objects.order_by('-sazba_start').first()
            self.fields['sazba_hodnota'].initial = latest.hodnota if latest else 0

        for field_name in ['termin', 'zakazka_start', 'zakazka_konec_predp', 'zakazka_konec_skut']:
            value = getattr(self.instance, field_name, None)
            if value:
                self.initial[field_name] = value.strftime('%Y-%m-%d')

        tail = [name for name in ('sjednana_cena', 'zaloha') if name in self.fields]
        head = [n for n in list(self.fields.keys()) if n not in tail]
        self.order_fields(head + tail)

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
        nova_hodnota = self.cleaned_data['sazba_hodnota']

        if zakazka.pk and zakazka.sazba_id and zakazka.sazba.hodnota == nova_hodnota:
            pass
        else:
            sazba = Sazba.objects.create(hodnota=nova_hodnota, sazba_start=now())
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
    # Hodinová sazba v editaci není povinná; u zaměstnanců (interních) ji ignorujeme.
    sazba_hod = forms.DecimalField(
        label='Hodinová sazba',
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={"min": "0", "class": "form-control"})
    )

    class Meta:
        model = Zamestnanec
        fields = ('username', 'jmeno', 'prijmeni', 'titul', 'is_admin',
                  'sazba_hod', 'rezie_hod', "typ_osoby", "mzda_mesic", "sazba_km")
        labels = {
            'username': 'Uživatelské jméno (přihlašovací)',
            'jmeno': 'Jméno',
            'prijmeni': 'Příjmení',
            'titul': 'Titul',
            'is_admin': 'Administrátor',
            'sazba_hod': 'Hodinová sazba',
            "typ_osoby": 'externista/zaměstnanec',
            "mzda_mesic": 'mzda/měsíc (vyplnit jen u zaměstnanců)',
            "sazba_km": 'sazba na kilometr',
            "rezie_hod": 'Režie na pracovníka (Kč/h)',
        }
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'jmeno': forms.TextInput(attrs={'class': 'form-control'}),
            'prijmeni': forms.TextInput(attrs={'class': 'form-control'}),
            'titul': forms.TextInput(attrs={'class': 'form-control'}),
            'is_admin': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            "typ_osoby": forms.Select(attrs={"class": "form-select"}),
            "mzda_mesic": forms.NumberInput(attrs={"min": "0", "class": "form-control"}),
            "sazba_km": forms.NumberInput(attrs={"min": "0", "class": "form-control"}),
            "rezie_hod": forms.NumberInput(attrs={"min": "0", "step": "0.01", "class": "form-control"}),
        }

    def clean(self):
        cleaned = super().clean()
        typ = cleaned.get("typ_osoby")
        sazba = cleaned.get("sazba_hod")
        # Externista musí mít hodinovou sazbu vyplněnou
        if typ == Zamestnanec.TYP_EXTERNAL and (sazba is None):
            self.add_error("sazba_hod", "Externista musí mít vyplněnou hodinovou sazbu.")
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        # U interních zaměstnanců sazbu neukládáme (bude se dopočítávat dynamicky)
        if obj.typ_osoby == Zamestnanec.TYP_EMPLOYEE:
            obj.sazba_hod = None
        if commit:
            obj.save()
        return obj



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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['text'].required = False  # <=== DŮLEŽITÉ
        self.fields['text'].empty_label = "—"

    def clean(self):
        cleaned_data = super().clean()
        text = cleaned_data.get("text")
        novy_text = cleaned_data.get("novy_text")

        if not text and not novy_text:
            raise forms.ValidationError("Vyplňte buď stávající rozsah nebo nový text.")

        return cleaned_data

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


class RozsahPraceInlineForm(forms.ModelForm):
    text_value = forms.CharField(
        label='Text rozsahu práce',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Zadejte text rozsahu'}),
        required=True,
    )

    class Meta:
        model = RozsahPrace
        # PK přidáme a rovnou ho schováme, ať se POSTne
        fields = ('id',)                               # ← důležité
        widgets = {'id': forms.HiddenInput()}          # ← důležité

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # chraň se proti KeyError, kdyby 'id' někdy nebylo
        if 'id' in self.fields:
            self.fields['id'].required = False

        if self.instance and getattr(self.instance, 'text_id', None) and self.instance.text:
            self.initial['text_value'] = self.instance.text.text

    def clean_text_value(self):
        val = (self.cleaned_data.get('text_value') or '').strip()
        if not val:
            raise forms.ValidationError("Text nesmí být prázdný.")
        return val

class RozsahPraceEditForm(forms.ModelForm):
    text_value = forms.CharField(
        label="Text rozsahu práce",
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = RozsahPrace
        fields = []  # nepoužíváme přímo žádná modelová pole

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.text:
            self.fields['text_value'].initial = self.instance.text.text


RozsahPraceEditFormSet = modelformset_factory(
    RozsahPrace,
    form=RozsahPraceEditForm,
    can_delete=True,        # ⬅️ umožní mazání
    extra=0                 # ⬅️ vždy jeden prázdný pro přidání
)


class EmployeeWeeklyPlanForm(forms.ModelForm):
    class Meta:
        model = Zamestnanec
        fields = ["plan_po", "plan_ut", "plan_st", "plan_ct", "plan_pa", "plan_so", "plan_ne"]
        labels = {
            "plan_po": "Pondělí (h)",
            "plan_ut": "Úterý (h)",
            "plan_st": "Středa (h)",
            "plan_ct": "Čtvrtek (h)",
            "plan_pa": "Pátek (h)",
            "plan_so": "Sobota (h)",
            "plan_ne": "Neděle (h)",
        }
        widgets = {
            "plan_po": forms.NumberInput(attrs={"step": "0.5", "min": "0", "max": "24", "class": "form-control"}),
            "plan_ut": forms.NumberInput(attrs={"step": "0.5", "min": "0", "max": "24", "class": "form-control"}),
            "plan_st": forms.NumberInput(attrs={"step": "0.5", "min": "0", "max": "24", "class": "form-control"}),
            "plan_ct": forms.NumberInput(attrs={"step": "0.5", "min": "0", "max": "24", "class": "form-control"}),
            "plan_pa": forms.NumberInput(attrs={"step": "0.5", "min": "0", "max": "24", "class": "form-control"}),
            "plan_so": forms.NumberInput(attrs={"step": "0.5", "min": "0", "max": "24", "class": "form-control"}),
            "plan_ne": forms.NumberInput(attrs={"step": "0.5", "min": "0", "max": "24", "class": "form-control"}),
        }

    def clean(self):
        cleaned = super().clean()
        for f in ["plan_po","plan_ut","plan_st","plan_ct","plan_pa","plan_so","plan_ne"]:
            val = cleaned.get(f)
            if val is None:
                continue
            if val < 0 or val > 24:
                self.add_error(f, "Hodnota musí být mezi 0 a 24 hodinami.")
        return cleaned


class OverheadRateForm(forms.ModelForm):
    class Meta:
        model = OverheadRate
        fields = ["valid_from", "rate_per_hour", "divisor", "note"]
        labels = {
            "valid_from": "Platí od",
            "rate_per_hour": "Režijní sazba (Kč/h)",
            "divisor": "Dělič (celofiremní)",
            "note": "Poznámka",
        }
        widgets = {
            "valid_from": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "rate_per_hour": forms.NumberInput(attrs={"step": "0.01", "min": "0", "class": "form-control"}),
            "divisor": forms.NumberInput(attrs={"step": "0.1", "min": "0.1", "class": "form-control"}),
            "note": forms.TextInput(attrs={"class": "form-control"}),
        }

    def clean_divisor(self):
        d = self.cleaned_data["divisor"]
        if d is None or d <= 0:
            raise forms.ValidationError("Dělič musí být kladný.")
        return d

    def clean_rate_per_hour(self):
        v = self.cleaned_data["rate_per_hour"]
        if v is None or v < 0:
            raise forms.ValidationError("Sazba musí být nezáporná.")
        return v

def _easter_sunday(year: int) -> date:
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
    return date(year, month, day)

def _cz_holidays(year: int) -> set[date]:
    """CZ státní svátky: fixní + Velikonoční pondělí (stejné jako ve views)."""
    easter_mon = _easter_sunday(year) + timedelta(days=1)
    fixed = {
        (1,1),(5,1),(5,8),(7,5),(7,6),(9,28),(10,28),(11,17),(12,24),(12,25),(12,26)
    }
    s = {date(year, m, d) for (m, d) in fixed}
    s.add(easter_mon)
    return s