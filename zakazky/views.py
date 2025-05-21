# views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from .forms import LoginForm, ZakazkaForm
from .models import Zakazka


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.get_user())
        return redirect('dashboard')

    return render(request, 'login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def dashboard_view(request):
    zakazky = Zakazka.objects.all().order_by('-id')
    return render(request, 'dashboard.html', {
        'zakazky': zakazky,
        'is_admin': request.user.is_admin
    })

@login_required
def create_zakazka_view(request):
    if not request.user.is_admin:
        return HttpResponseForbidden("Pouze administrátor může vytvářet zakázky.")

    if request.method == 'POST':
        form = ZakazkaForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = ZakazkaForm()

    return render(request, 'zakazka_form.html', {'form': form})