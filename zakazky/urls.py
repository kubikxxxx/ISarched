from django.urls import path
from .views import login_view, logout_view, dashboard_view, create_zakazka_view
from django.contrib.auth.decorators import login_required

urlpatterns = [
    path('', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('dashboard/', login_required(dashboard_view), name='dashboard'),
    path('zakazka/create/', login_required(create_zakazka_view), name='create_zakazka'),
]

