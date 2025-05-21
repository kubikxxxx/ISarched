
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import Zakazka

class LoginForm(AuthenticationForm):
    username = forms.CharField(label='Uživatelské jméno')
    password = forms.CharField(widget=forms.PasswordInput, label='Heslo')

class ZakazkaForm(forms.ModelForm):
    class Meta:
        model = Zakazka
        exclude = ['zakazka_konec_predp', 'zakazka_start', 'zakazka_konec_skut']