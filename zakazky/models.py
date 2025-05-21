# models.py
from django.db import models
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
    jmeno = models.TextField()
    prijmeni = models.TextField()
    is_admin = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    objects = ZamestnanecManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['jmeno', 'prijmeni']

    class Meta:
        db_table = 'Zamestnanec'
        managed = True

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

    class Meta:
        db_table = 'Subdodavatel'
        managed = True

    def __str__(self):
        return f"{self.titul_pred or ''} {self.jmeno} {self.prijmeni} {self.titul_za or ''}".strip()


class Subdodavka(models.Model):
    nazev = models.TextField()
    aktivni = models.BooleanField()

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
    termin = models.DateTimeField()
    zakazka_konec_predp = models.DateTimeField(null=True, blank=True)
    zakazka_start = models.DateTimeField(null=True, blank=True)
    zakazka_konec_skut = models.DateTimeField(null=True, blank=True)
    predpokladany_cas = models.IntegerField()
    mesto = models.TextField()
    ulice = models.TextField()
    psc = models.TextField()
    orientacni_naklady = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    plna_moc = models.BooleanField()
    hip = models.TextField()
    popis_zadani = models.TextField()

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

    class Meta:
        db_table = 'ZakazkaZamestnanec'
        managed = True
        unique_together = (('zakazka', 'zamestnanec', 'den_prace'),)

    def __str__(self):
        return f"{self.zakazka} – {self.zamestnanec} – {self.den_prace}"


class ZamestnanecZakazka(models.Model):
    zamestnanec = models.ForeignKey('Zamestnanec', on_delete=models.CASCADE, db_column='ID_Zamestnanec')
    zakazka = models.ForeignKey('Zakazka', on_delete=models.CASCADE, db_column='ID_Zakazka')
    prideleno_hodin = models.IntegerField()
    premie_predpoklad = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    premie_skutecnost = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    datum_prideleni = models.DateTimeField(null=True, blank=True)
    popis = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'ZamestnanecZakazka'
        managed = True
        unique_together = (('zamestnanec', 'zakazka'),)

    def __str__(self):
        return f"{self.zamestnanec} – {self.zakazka}"
