from django.urls import path
from .views import login_view, logout_view, homepage_view, create_zakazka_view, employee_create_view, \
    client_create_view, delete_zakazka_view, edit_zakazka_view, client_edit_view, client_note_create_view, \
    zakazka_subdodavky_view, create_subdodavatel_view, create_subdodavka_view, uredni_zapis_create_view, \
    uredni_zapis_edit_view, prirazeni_view, upravit_prirazeni_view, vykaz_create_view
from django.contrib.auth.decorators import login_required

urlpatterns = [
    path('', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('homepage/', login_required(homepage_view), name='homepage'),
    path('zakazka/create/', login_required(create_zakazka_view), name='create_zakazka'),
    path('employees/create/', login_required(employee_create_view), name='employee_create'),
    path('clients/create/', login_required(client_create_view), name='client_create'),
    path('zakazka/<int:zakazka_id>/edit/', edit_zakazka_view, name='edit_zakazka'),
    path('zakazka/<int:zakazka_id>/delete/', delete_zakazka_view, name='delete_zakazka'),
    path('clients/<int:klient_id>/edit/', client_edit_view, name='client_edit'),
    path('clients/<int:klient_id>/note/', client_note_create_view, name='client_add_note'),
    path('zakazka/<int:zakazka_id>/subdodavky/', zakazka_subdodavky_view, name='zakazka_subdodavky'),
    path('subdodavka/create/', create_subdodavka_view, name='create_subdodavka'),
    path('subdodavatel/create/', create_subdodavatel_view, name='create_subdodavatel'),
    path('zakazka/<int:zakazka_id>/zapis/', uredni_zapis_create_view, name='uredni_zapis_create'),
    path('zakazka/<int:zakazka_id>/zapis/', uredni_zapis_create_view, name='uredni_zapis_create'),
    path('zapis/<int:zapis_id>/edit/', uredni_zapis_edit_view, name='uredni_zapis_edit'),
    path('zakazka/<int:zakazka_id>/prirazeni/', prirazeni_view, name='prirazeni_view'),
    path('prirazeni/<int:prirazeni_id>/edit/', upravit_prirazeni_view, name='upravit_prirazeni'),
    path('zakazka/<int:zakazka_id>/vykaz/create/', vykaz_create_view, name='vykaz_create'),
]
