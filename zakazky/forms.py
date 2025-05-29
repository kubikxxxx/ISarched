from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.forms import UserCreationForm
from django.utils.timezone import now
from .models import Zakazka, Zamestnanec, Klient, Sazba, KlientPoznamka, Subdodavka, Subdodavatel, UredniZapis, \
    ZakazkaZamestnanec


class LoginForm(AuthenticationForm):
    username = forms.CharField(label='Uživatelské jméno')
    password = forms.CharField(widget=forms.PasswordInput, label='Heslo')


class ZakazkaForm(forms.ModelForm):
    sazba_hodnota = forms.DecimalField(label='Sazba (Kč)', max_digits=18, decimal_places=2)
    hip = forms.ModelChoiceField(
        queryset=Zamestnanec.objects.all(),
        required=False,
        label="HIP"
    )

    class Meta:
        model = Zakazka
        exclude = ['sazba', 'zakazka_konec_predp', 'zakazka_konec_skut']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            latest = Sazba.objects.latest('sazba_start')
            self.fields['sazba_hodnota'].initial = latest.hodnota
        except Sazba.DoesNotExist:
            self.fields['sazba_hodnota'].initial = 0

    def save(self, commit=True):
        zakazka = super().save(commit=False)

        # vytvoříme novou sazbu
        sazba = Sazba.objects.create(
            hodnota=self.cleaned_data['sazba_hodnota'],
            sazba_start=now()
        )

        zakazka.sazba = sazba

        if commit:
            zakazka.save()

        return zakazka


class EmployeeForm(UserCreationForm):
    jmeno = forms.CharField(label='Jméno', max_length=255)
    prijmeni = forms.CharField(label='Příjmení', max_length=255)
    titul = forms.CharField(label='Titul', max_length=255, required=False)
    is_admin = forms.BooleanField(label='Administrátor', required=False)

    class Meta:
        model = Zamestnanec
        fields = ('username', 'jmeno', 'prijmeni', 'titul', 'is_admin', 'sazba_hod')


class ClientForm(forms.ModelForm):
    class Meta:
        model = Klient
        exclude = []


class KlientPoznamkaForm(forms.ModelForm):
    class Meta:
        model = KlientPoznamka
        fields = ['text']


class SubdodavkaForm(forms.ModelForm):
    class Meta:
        model = Subdodavka
        fields = ['nazev', 'aktivni']


class SubdodavatelForm(forms.ModelForm):
    class Meta:
        model = Subdodavatel
        fields = ['titul_pred', 'jmeno', 'prijmeni', 'titul_za']


class UredniZapisForm(forms.ModelForm):
    class Meta:
        model = UredniZapis
        fields = ['popis', 'datum', 'termin_do', 'splneno']


class VykazForm(forms.ModelForm):
    class Meta:
        model = ZakazkaZamestnanec
        fields = ['den_prace', 'cas_od', 'cas_do', 'popis', 'najete_km']
        widgets = {
            'den_prace': forms.DateInput(attrs={'type': 'date'}),
            'cas_od': forms.TimeInput(attrs={'type': 'time'}),
            'cas_do': forms.TimeInput(attrs={'type': 'time'}),
        }
