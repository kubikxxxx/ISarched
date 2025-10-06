from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
import datetime as dt
import calendar
from django.db.models import Sum
from django.utils.timezone import localdate

from .models import OverheadRate, PlanDen, ZakazkaZamestnanec, Zamestnanec, ZakazkaSubdodavka, Zakazka


# --- Svátky ČR (stejně jako máš ve views, tady samostatně) -------------------
def _easter_sunday(year: int) -> dt.date:
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
    return dt.date(year, month, day)

def cz_holidays_for_year(year: int) -> set[dt.date]:
    fixed = {(1,1),(5,1),(5,8),(7,5),(7,6),(9,28),(10,28),(11,17),(12,24),(12,25),(12,26)}
    s = {dt.date(year, m, d) for (m, d) in fixed}
    s.add(_easter_sunday(year) + dt.timedelta(days=1))  # Velikonoční pondělí
    return s

def is_workday(day: dt.date) -> bool:
    return (day.weekday() < 5) and (day not in cz_holidays_for_year(day.year))

# --- Režijní sazba v čase ----------------------------------------------------
def overhead_rate_on(day: dt.date) -> Decimal:
    rec = OverheadRate.objects.filter(valid_from__lte=day).order_by("-valid_from").first()
    return Decimal(str(rec.rate_per_hour)) if rec else Decimal("0")

def overhead_worker_hour(emp: Zamestnanec, day: dt.date) -> Decimal:
    """Režie na osobu a hodinu: sazba / (overhead_divisor or 1)."""
    div = Decimal(str(getattr(emp, "overhead_divisor", 1) or 1))
    if div <= 0:
        div = Decimal("1")
    return (overhead_rate_on(day) / div).quantize(Decimal("0.01"))

def cost_hour(emp: Zamestnanec, day: dt.date) -> Decimal:
    """Hodinový náklad osoby v daný den: osobní hodinovka + režijní přirážka."""
    base = Decimal(str(getattr(emp, "sazba_hod", 0) or 0))
    return (base + overhead_worker_hour(emp, day)).quantize(Decimal("0.01"))

# --- Plán vs. skutečnost ------------------------------------------------------
_WD = ["po", "ut", "st", "ct", "pa", "so", "ne"]

def weekly_plan_value(emp: Zamestnanec, day: dt.date) -> Decimal:
    fld = f"plan_{_WD[day.weekday()]}"
    v = getattr(emp, fld, None)
    if v is None:
        return Decimal("8") if day.weekday() < 5 else Decimal("0")
    return Decimal(str(v))

def plan_for_day(emp: Zamestnanec, day: dt.date) -> Decimal:
    # svátek → 0, pokud není explicitní override
    if day in cz_holidays_for_year(day.year):
        default = Decimal("0")
    else:
        default = weekly_plan_value(emp, day)
    ov = PlanDen.objects.filter(zamestnanec=emp, datum=day).values_list("plan_hodin", flat=True).first()
    return Decimal(str(ov)) if ov is not None else default

def planned_hours(emp: Zamestnanec, start: dt.date, end: dt.date) -> Decimal:
    total = Decimal("0")
    d = start
    while d <= end:
        total += plan_for_day(emp, d)
        d += dt.timedelta(days=1)
    return total

def D(x) -> Decimal:
    return Decimal("0") if x in (None, "") else Decimal(str(x))

def _hours_between(d: dt.date, t_from, t_to) -> Decimal:
    """Vrátí počet hodin čistě jako Decimal (žádné floaty)."""
    if not (t_from and t_to):
        return Decimal("0")
    start = dt.datetime.combine(d, t_from)
    end   = dt.datetime.combine(d, t_to)
    if end <= start:
        return Decimal("0")
    secs = D((end - start).total_seconds())   # převést na Decimal
    return (secs / Decimal("3600")).quantize(Decimal("0.01"))

def actual_hours(emp: Zamestnanec, start: dt.date, end: dt.date) -> Decimal:
    qs = ZakazkaZamestnanec.objects.filter(zamestnanec=emp, den_prace__gte=start, den_prace__lte=end)
    total = Decimal("0")
    for v in qs:
        total += _hours_between(v.den_prace, v.cas_od, v.cas_do)
    return total.quantize(Decimal("0.01"))

M2 = Decimal("0.01")

def q2(x: Decimal | float | int | None) -> Decimal:
    return (Decimal(str(x or 0))).quantize(M2, rounding=ROUND_HALF_UP)

def estimated_company_hour_cost(ref_day: dt.date) -> Decimal:
    """Odhad celkového nákladu/hod firmy = průměr cost_hour všech aktivních zaměstnanců (EMP).
       Když nic není, vezmeme 650 Kč/h jako rozumný default."""
    emps = Zamestnanec.objects.filter(is_active=True)
    if not emps.exists():
        return Decimal("650.00")
    from .helpers import cost_hour  # re-use funkce
    s = Decimal("0")
    n = 0
    for e in emps:
        s += cost_hour(e, ref_day)
        n += 1
    return (s / max(n, 1)).quantize(M2)

def compute_project_finance(z: Zakazka) -> dict:
    """
    Spočítá všechny ukazatele pro detail zakázky (za celé období zakázky).
    Skutečné náklady počítá po DNECH: hodiny × (sazba_hod + režie_na_osobu_v_daný_den),
    cestovné = km × sazba_km; subdodávky = suma 'cena' kde fakturuje_arched=True.
    """
    today = dt.date.today()

    # --- VÝKAZY (skutečné hodiny/km) ----------------------------------------
    vqs = (ZakazkaZamestnanec.objects
           .select_related("zamestnanec")
           .filter(zakazka=z)
           .order_by("den_prace"))

    # kumulace po zaměstnancích i celkově
    by_emp = defaultdict(lambda: {
        "emp": None, "hours": Decimal("0"), "km": Decimal("0"),
        "labor": Decimal("0"), "travel": Decimal("0")
    })

    from .helpers import _hours_between, cost_hour  # tvoje už existující funkce

    total_hours = Decimal("0")
    total_km = Decimal("0")
    total_labor = Decimal("0")
    total_travel = Decimal("0")

    for v in vqs:
        hrs = _hours_between(v.den_prace, v.cas_od, v.cas_do)  # už vrací Decimal
        if hrs <= 0:
            continue
        km = Decimal(str(v.najete_km or 0))
        ch = cost_hour(v.zamestnanec, v.den_prace)            # Kč/h v daný den
        labor = (hrs * ch)
        travel = km * Decimal(str(v.zamestnanec.sazba_km or 0))

        rec = by_emp[v.zamestnanec_id]
        rec["emp"] = v.zamestnanec
        rec["hours"] += hrs
        rec["km"] += km
        rec["labor"] += labor
        rec["travel"] += travel

        total_hours += hrs
        total_km += km
        total_labor += labor
        total_travel += travel

    # --- SUBDODÁVKY (které platí Arched) ------------------------------------
    subs_arched = ZakazkaSubdodavka.objects.filter(zakazka=z, fakturuje_arched=True)\
                                           .values_list("cena", flat=True)
    total_subs = sum((Decimal(str(c or 0)) for c in subs_arched), Decimal("0"))

    # --- PŘÍJMY --------------------------------------------------------------
    agreed = Decimal(str(z.sjednana_cena or 0))

    # --- SKUTEČNÁ HOD. SAZBA (čistý výnos/hod) -------------------------------
    actual_hour_rate = None
    if total_hours > 0:
        actual_hour_rate = ((agreed - total_subs) / total_hours).quantize(M2)

    # --- PŘEDPOKLÁDANÉ -------------------------------------------------------
    pred_hours = Decimal(str(z.predpokladany_cas or 0))
    pred_rate = Decimal(str(getattr(getattr(z, "sazba", None), "hodnota", 0) or 0))
    est_cost_h = estimated_company_hour_cost(today)   # např. ~ 600–700 Kč/h
    predicted_profit = None
    if pred_hours > 0 and pred_rate > 0:
        predicted_profit = (pred_hours * (pred_rate - est_cost_h)).quantize(M2)

    # --- SKUTEČNÝ ZISK -------------------------------------------------------
    actual_profit = (agreed - total_subs - total_labor - total_travel).quantize(M2)

    # --- ROZDÍL --------------------------------------------------------------
    profit_diff = None
    if predicted_profit is not None:
        profit_diff = (actual_profit - predicted_profit).quantize(M2)

    # pro tabulku po osobách
    emp_rows = []
    for rec in by_emp.values():
        s = (rec["labor"] + rec["travel"]).quantize(M2)
        emp_rows.append({
            "emp": rec["emp"],
            "hours": rec["hours"].quantize(M2),
            "km": rec["km"].quantize(M2),
            "labor": rec["labor"].quantize(M2),
            "travel": rec["travel"].quantize(M2),
            "sum": s,
        })
    emp_rows.sort(key=lambda r: (r["sum"], r["hours"]), reverse=True)

    return {
        # celky
        "total_hours": total_hours.quantize(M2),
        "total_km": total_km.quantize(M2),
        "total_labor": total_labor.quantize(M2),
        "total_travel": total_travel.quantize(M2),
        "total_subs": total_subs.quantize(M2),
        "agreed": agreed.quantize(M2),
        # sazby
        "pred_rate": pred_rate.quantize(M2),
        "actual_hour_rate": actual_hour_rate,
        "est_cost_hour": est_cost_h,
        # zisky
        "predicted_profit": predicted_profit,
        "actual_profit": actual_profit,
        "profit_diff": profit_diff,
        # přehled po osobách
        "emp_rows": emp_rows,
    }