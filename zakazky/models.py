# models.py
from datetime import datetime

from django.conf import settings
from django.db import models
from django.utils.timezone import now
from simple_history.models import HistoricalRecords
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager



class ZamestnanecManager(BaseUserManager):
    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError("Uživatel musí mít uživatelské jméno")
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault('is_admin', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(username, password, **extra_fields)


class Zamestnanec(AbstractBaseUser, PermissionsMixin):
    username = models.CharField(max_length=255, unique=True)
    jmeno = models.CharField(max_length=255)
    prijmeni = models.CharField(max_length=255)
    titul = models.CharField(max_length=50, blank=True, null=True)
    datum_nastup = models.DateTimeField(default=now)
    sazba_hod = models.DecimalField(max_digits=18, decimal_places=2)
    sazba_km = models.DecimalField(max_digits=18, decimal_places=2, blank=True, null=True)
    is_admin = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    banka_hodin = models.DecimalField(
        max_digits=6, decimal_places=2, default=0,
        help_text="+ znamená nadpracováno, − znamená dluh hodin"
    )
    plan_po = models.DecimalField(max_digits=4, decimal_places=2, default=8)
    plan_ut = models.DecimalField(max_digits=4, decimal_places=2, default=8)
    plan_st = models.DecimalField(max_digits=4, decimal_places=2, default=8)
    plan_ct = models.DecimalField(max_digits=4, decimal_places=2, default=8)
    plan_pa = models.DecimalField(max_digits=4, decimal_places=2, default=8)
    plan_so = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    plan_ne = models.DecimalField(max_digits=4, decimal_places=2, default=0)

    TYP_EMPLOYEE = "EMP"
    TYP_EXTERNAL = "EXT"
    TYP_CHOICES = (
        (TYP_EMPLOYEE, "Zaměstnanec"),
        (TYP_EXTERNAL, "Externista"),
    )

    typ_osoby = models.CharField(
        max_length=3,
        choices=TYP_CHOICES,
        default=TYP_EMPLOYEE,
        help_text="Rozlišení pro kalkulaci nákladů."
    )

    mzda_mesic = models.DecimalField(
        max_digits=12, decimal_places=2,
        null=True, blank=True,
        help_text="Měsíční mzda (Kč). Použije se pro zaměstnance."
    )

    rezie_hod = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                    help_text="Osobní režie pracovníka (Kč/h).")

    objects = ZamestnanecManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['jmeno', 'prijmeni', 'datum_nastup', 'sazba_hod']

    class Meta:
        db_table = 'Zamestnanec'

    def __str__(self):
        return f"{self.jmeno} {self.prijmeni}"

    @property
    def is_staff(self):
        return self.is_admin


class Klient(models.Model):
    nazev = models.CharField(max_length=255)
    sidlo_mesto = models.CharField(max_length=255)
    sidlo_ulice = models.CharField(max_length=255)
    sidlo_psc = models.CharField(max_length=255)
    ico = models.CharField(max_length=50)
    dic = models.CharField(max_length=20, blank=True, null=True, verbose_name="DIČ")
    email = models.EmailField(max_length=255)
    telefon = models.CharField(max_length=50)
    fakturacni_nazev = models.CharField(max_length=255, null=True, blank=True)
    fakturacni_mesto = models.CharField(max_length=255, null=True, blank=True)
    fakturacni_ulice = models.CharField(max_length=255, null=True, blank=True)
    fakturacni_psc = models.CharField(max_length=255, null=True, blank=True)
    fakturacni_ico = models.CharField(max_length=50, null=True, blank=True)
    fakturacni_email = models.EmailField(max_length=255, null=True, blank=True)
    fakturacni_telefon = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        db_table = 'Klient'
        managed = True

    def __str__(self):
        return self.nazev


class KlientPoznamka(models.Model):
    datum = models.DateTimeField()
    text = models.TextField()
    klient = models.ForeignKey('Klient', on_delete=models.CASCADE, db_column='KlientID')

    class Meta:
        db_table = 'KlientPoznamka'
        managed = True

    def __str__(self):
        return f"{self.klient.nazev} – {self.datum:%Y-%m-%d}"


class Sazba(models.Model):
    hodnota = models.DecimalField(max_digits=18, decimal_places=2)
    sazba_start = models.DateTimeField(db_column='SazbaStart')

    class Meta:
        db_table = 'Sazba'
        managed = True

    def __str__(self):
        return f"{self.hodnota} od {self.sazba_start:%Y-%m-%d}"


class Subdodavatel(models.Model):
    titul_pred = models.TextField(null=True, blank=True)
    jmeno = models.TextField()
    prijmeni = models.TextField()
    titul_za = models.TextField(null=True, blank=True)
    telefon = models.CharField(max_length=50, null=True, blank=True)
    email = models.EmailField(max_length=255, null=True, blank=True)
    ico = models.CharField("IČO", max_length=20, null=True, blank=True)
    dic = models.CharField("DIČ", max_length=20, null=True, blank=True)

    class Meta:
        db_table = 'Subdodavatel'
        managed = True

    def __str__(self):
        return f"{self.titul_pred or ''} {self.jmeno} {self.prijmeni} {self.titul_za or ''}".strip()



class Subdodavka(models.Model):
    nazev = models.TextField(max_length=50)
    aktivni = models.BooleanField(default=1)

    class Meta:
        db_table = 'Subdodavka'
        managed = True

    def __str__(self):
        return self.nazev

class Zakazka(models.Model):
    klient = models.ForeignKey('Klient', on_delete=models.CASCADE, db_column='ID_Klient')
    sazba = models.ForeignKey('Sazba', on_delete=models.SET_NULL, null=True, blank=True, db_column='ID_Sazba')
    zakazka_cislo = models.TextField(db_column='ZakazkaCislo')
    nazev = models.TextField()

    termin = models.DateTimeField(default=datetime(2025, 9, 1, 0, 0))  # <-- pevné výchozí datum
    zakazka_start = models.DateTimeField(null=True, blank=True)
    zakazka_konec_predp = models.DateTimeField(null=True, blank=True)
    zakazka_konec_skut = models.DateTimeField(null=True, blank=True)
    predpokladany_cas = models.IntegerField()
    misto_stavby = models.TextField()
    orientacni_naklady = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    plna_moc = models.BooleanField()
    hip = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name="HIP")
    popis_zadani = models.TextField()
    sjednana_cena = models.DecimalField(
        "Sjednaná cena",
        max_digits=18,
        decimal_places=2,
        null=True,      # ← nepovinné
        blank=True,     # ← nepovinné
    )
    zaloha = models.DecimalField(
        "Záloha",
        max_digits=18,
        decimal_places=2,
        null=True,      # ← nepovinné
        blank=True,     # ← nepovinné
    )
    orientacni_hodinove_naklady = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Hodinový náklad pro předpokládaný zisk."
    )

    class Meta:
        db_table = 'Zakazka'
        managed = True

    def __str__(self):
        return f"{self.zakazka_cislo} – {self.nazev}"



class UredniZapis(models.Model):
    zakazka = models.ForeignKey('Zakazka', on_delete=models.CASCADE, db_column='ZakazkaId')
    popis = models.TextField()
    datum = models.DateTimeField()
    termin_do = models.DateTimeField(null=True, blank=True)
    splneno = models.BooleanField()
    vytvoril = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='zaznamy_uredni',
        verbose_name="Záznam přidal"
    )
    history = HistoricalRecords()

    class Meta:
        db_table = 'UredniZapis'
        managed = True

    def __str__(self):
        return f"{self.zakazka} – {self.popis[:30]}…"


class ZakazkaSubdodavka(models.Model):
    zakazka = models.ForeignKey('Zakazka', on_delete=models.CASCADE, db_column='ID_Zakazka')
    subdodavka = models.ForeignKey('Subdodavka', on_delete=models.DO_NOTHING, db_column='ID_Subdodavka')
    subdodavatel = models.ForeignKey('Subdodavatel', on_delete=models.DO_NOTHING, db_column='ID_Subdodavatel')
    cena = models.DecimalField(max_digits=18, decimal_places=2)
    navyseni = models.DecimalField(max_digits=18, decimal_places=2)
    fakturuje_klientovi = models.BooleanField()
    fakturuje_arched = models.BooleanField()

    class Meta:
        db_table = 'ZakazkaSubdodavka'
        managed = True
        unique_together = (('zakazka', 'subdodavka', 'subdodavatel'),)

    def __str__(self):
        return f"{self.zakazka} – {self.subdodavka} – {self.subdodavatel}"


class ZakazkaZamestnanec(models.Model):
    zakazka = models.ForeignKey('Zakazka', on_delete=models.CASCADE, db_column='ID_Zakazka')
    zamestnanec = models.ForeignKey('Zamestnanec', on_delete=models.CASCADE, db_column='ID_Zamestnanec')
    den_prace = models.DateField(db_column='DenPrace')
    cas_od = models.TimeField(null=True, blank=True, db_column='CasOd')
    cas_do = models.TimeField(null=True, blank=True, db_column='CasDo')
    popis = models.TextField(null=True, blank=True)
    najete_km = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    history = HistoricalRecords()

    class Meta:
        db_table = 'ZakazkaZamestnanec'
        managed = True

    def __str__(self):
        return f"{self.zakazka} – {self.zamestnanec} – {self.den_prace}"


class ZamestnanecZakazka(models.Model):
    zamestnanec = models.ForeignKey('Zamestnanec', on_delete=models.CASCADE, db_column='ID_Zamestnanec')
    zakazka = models.ForeignKey('Zakazka', on_delete=models.CASCADE, db_column='ID_Zakazka', related_name='prirazeni')
    prideleno_hodin = models.IntegerField()
    premie_predpoklad = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    premie_skutecnost = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    datum_prideleni = models.DateTimeField(null=True, blank=True)
    popis = models.TextField(null=True, blank=True)
    skryta = models.BooleanField(default=False)

    class Meta:
        db_table = 'ZamestnanecZakazka'
        managed = True
        unique_together = (('zamestnanec', 'zakazka'),)

    def __str__(self):
        return f"{self.zamestnanec} – {self.zakazka}"

class RozsahText(models.Model):
    text = models.TextField(unique=True)

    class Meta:
        db_table = 'RozsahText'

    def __str__(self):
        return self.text[:50]  # první znaky pro výpis


class RozsahPrace(models.Model):
    zakazka = models.ForeignKey(Zakazka, on_delete=models.CASCADE)
    text = models.ForeignKey(RozsahText, on_delete=models.CASCADE, null=True, blank=True)
    vytvoril = models.ForeignKey(Zamestnanec, on_delete=models.SET_NULL, null=True)
    datum_vytvoreni = models.DateTimeField(default=now)
    splneno = models.BooleanField(default=False)
    datum_splneni = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'RozsahPrace'

    def __str__(self):
        return f"{self.text} – {self.zakazka}"

class UzaverkaMesice(models.Model):
    zamestnanec = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rok = models.IntegerField()
    mesic = models.IntegerField()  # 1–12
    delta_hodin = models.DecimalField(max_digits=6, decimal_places=2)
    vytvoreno = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("zamestnanec", "rok", "mesic")

class PlanDen(models.Model):
    zamestnanec = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    datum = models.DateField()
    plan_hodin = models.DecimalField(max_digits=4, decimal_places=2)

    class Meta:
        unique_together = ("zamestnanec", "datum")
        indexes = [models.Index(fields=["zamestnanec", "datum"])]

    def __str__(self):
        return f"{self.zamestnanec} – {self.datum}: {self.plan_hodin} h"


class OverheadRate(models.Model):
    """
    Režijní náklad firmy v Kč / 1 hodinu, s datem účinnosti.
    Pro výpočet měsíce se pro každý den vezme sazba platná v ten den.
    """
    valid_from = models.DateField(help_text="Platí od tohoto data (včetně).")
    rate_per_hour = models.DecimalField(max_digits=10, decimal_places=2, help_text="Kč za hodinu.")
    divisor = models.DecimalField(
        max_digits=6, decimal_places=2, default=1,
        help_text="Celofiremní dělič režijní sazby (režie/worker = sazba / divisor)."
    )
    note = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ["-valid_from"]
        indexes = [models.Index(fields=["valid_from"])]

    def __str__(self):
        return f"{self.valid_from}: {self.rate_per_hour} Kč/h"