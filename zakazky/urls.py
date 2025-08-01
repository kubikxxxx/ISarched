from django.urls import path
from .views import login_view, logout_view, homepage_view, create_zakazka_view, employee_create_view, \
    client_create_view, delete_zakazka_view, edit_zakazka_view, client_edit_view, client_note_create_view, \
    zakazka_subdodavky_view, create_subdodavatel_view, create_subdodavka_view, uredni_zapis_create_view, \
    uredni_zapis_edit_view, prirazeni_view, upravit_prirazeni_view, vykaz_create_view, edit_subdodavka_view, \
    ukoncit_zakazku_view, toggle_rozsah_splneno, change_password_view, nacti_ares, \
    over_dph_spolehlivost, edit_subdodavatel_view, edit_employee_view, toggle_viditelnost_view, historie_zapisu_view, \
    vykaz_edit_view, vykaz_history_view, zakazka_rozsahy_view
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
    path('subdodavka/<int:subdodavka_id>/edit/', edit_subdodavka_view, name='edit_subdodavka'),
    path('subdodavatel/create/', create_subdodavatel_view, name='create_subdodavatel'),
    path('zakazka/<int:zakazka_id>/zapis/', uredni_zapis_create_view, name='uredni_zapis_create'),
    path('zakazka/<int:zakazka_id>/zapis/', uredni_zapis_create_view, name='uredni_zapis_create'),
    path('zapis/<int:zapis_id>/edit/', uredni_zapis_edit_view, name='uredni_zapis_edit'),
    path('zakazka/<int:zakazka_id>/prirazeni/', prirazeni_view, name='prirazeni_view'),
    path('prirazeni/<int:prirazeni_id>/edit/', upravit_prirazeni_view, name='upravit_prirazeni'),
    path('zakazka/<int:zakazka_id>/vykaz/create/', vykaz_create_view, name='vykaz_create'),
    path('zakazka/<int:zakazka_id>/ukoncit/', ukoncit_zakazku_view, name='ukoncit_zakazku'),
    path('rozsah/<int:pk>/toggle/', toggle_rozsah_splneno, name='toggle_rozsah_splneno'),
    path('nacti-ares/', nacti_ares, name='nacti_ares'),
    path('over-dph/', over_dph_spolehlivost, name='over_dph'),
    path('subdodavatel/<int:subdodavatel_id>/edit/', edit_subdodavatel_view, name='edit_subdodavatel'),
    path('zamestnanec/<int:zamestnanec_id>/edit/', edit_employee_view, name='employee_edit'),
    path('zamestnanec/<int:zamestnanec_id>/password/', change_password_view, name='employee_password_change'),
    path('toggle-viditelnost/<int:prirazeni_id>/', toggle_viditelnost_view, name='toggle_viditelnost'),
    path('zapis/<int:zapis_id>/historie/', historie_zapisu_view, name='zapis_historie'),
    path('vykaz/<int:vykaz_id>/edit/', vykaz_edit_view, name='vykaz_edit'),
    path('vykaz/<int:vykaz_id>/historie/', vykaz_history_view, name='vykaz_historie'),
    path('zakazka/<int:zakazka_id>/rozsahy/', zakazka_rozsahy_view, name='zakazka_rozsahy'),

]
