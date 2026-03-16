from __future__ import annotations
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
import datetime as dt
import calendar

from django.utils.timezone import localdate
from django.db.models import Sum

from .models import ZakazkaZamestnanec, Zakazka, Zamestnanec
from .helpers import planned_hours, _hours_between


def build_statistiky_context(scope: str, ym: str | None = None, y: int | None = None,
                            cutoff: dt.date | None = None) -> dict:
    """
    Vrátí context přesně pro statistiky.html, ale spočtený jen DO cutoff (default = včerejšek).
    """
    ZERO = Decimal("0")

    if cutoff is None:
        cutoff = localdate() - dt.timedelta(days=1)

    def month_bounds(year: int, month: int):
        last = calendar.monthrange(year, month)[1]
        return dt.date(year, month, 1), dt.date(year, month, last)

    def month_nav(y_: int, m_: int):
        prev_y, prev_m = (y_ - 1, 12) if m_ == 1 else (y_, m_ - 1)
        next_y, next_m = (y_ + 1, 1) if m_ == 12 else (y_, m_ + 1)
        return f"{prev_y:04d}-{prev_m:02d}", f"{next_y:04d}-{next_m:02d}"

    # --- období (stejné jako ve view, jen místo today používáme cutoff)
    prev_ym = next_ym = prev_y = next_y = ""
    ym_for_template = ""
    y_for_template = ""

    scope = (scope or "month").lower()

    if scope == "year":
        year = int(y or cutoff.year)
        first_day = dt.date(year, 1, 1)
        last_day = dt.date(year, 12, 31)
        calc_until = min(last_day, cutoff)
        prev_y, next_y = str(year - 1), str(year + 1)
        y_for_template = year

    elif scope == "all":
        first_v = ZakazkaZamestnanec.objects.order_by("den_prace").values_list("den_prace", flat=True).first()
        first_day = first_v or cutoff
        last_day = cutoff
        calc_until = cutoff

    else:  # month
        if ym:
            year, month = map(int, ym.split("-"))
        else:
            year, month = cutoff.year, cutoff.month

        first_day, last_day = month_bounds(year, month)
        calc_until = min(last_day, cutoff)

        prev_ym, next_ym = month_nav(year, month)
        ym_for_template = f"{year:04d}-{month:02d}"

    # --- efektivní hodinovka (když chybí sazba_hod)
    def _as_dec(val, default="0"):
        try:
            return Decimal(str(val))
        except Exception:
            return Decimal(default)

    def _effective_rate_h(emp, period_start: dt.date, period_end: dt.date) -> Decimal:
        base = _as_dec(getattr(emp, "sazba_hod", 0), "0")
        if base > ZERO:
            return base

        plan_h = planned_hours(emp, period_start, period_end) or ZERO
        if plan_h <= ZERO:
            return ZERO

        monthly_fields = ("mzda_mesic", "mesicni_mzda", "mzda", "plat_mesic", "salary_monthly")
        monthly_wage = None
        for f in monthly_fields:
            if hasattr(emp, f):
                val = getattr(emp, f)
                if val is not None:
                    v = _as_dec(val, None)
                    if v is not None and v > ZERO:
                        monthly_wage = v
                        break

        if monthly_wage is None:
            return ZERO

        return (monthly_wage / plan_h).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # --- výkazy v období (jen do calc_until = cutoff)
    qs = (
        ZakazkaZamestnanec.objects
        .filter(den_prace__gte=first_day, den_prace__lte=calc_until)
        .select_related("zamestnanec", "zakazka", "zakazka__klient", "zakazka__sazba")
        .order_by("den_prace")
    )

    workh_by_emp: dict[int, Decimal] = {}
    km_by_emp: dict[int, Decimal] = {}

    for v in qs:
        hrs = _hours_between(v.den_prace, v.cas_od, v.cas_do)
        try:
            hrs = Decimal(str(hrs))
        except Exception:
            hrs = ZERO
        workh_by_emp[v.zamestnanec_id] = workh_by_emp.get(v.zamestnanec_id, ZERO) + hrs

        km = Decimal(str(v.najete_km or 0))
        km_by_emp[v.zamestnanec_id] = km_by_emp.get(v.zamestnanec_id, ZERO) + km

    # --- Mzdy zaměstnanci
    employees_rows = []
    for emp in Zamestnanec.objects.filter(is_active=True, typ_osoby=Zamestnanec.TYP_EMPLOYEE):
        plan_h = planned_hours(emp, first_day, calc_until) or ZERO
        rate_h = _effective_rate_h(emp, first_day, calc_until)
        mzda = (plan_h * rate_h).quantize(Decimal("0.01"))

        km_sum = km_by_emp.get(emp.id, ZERO)
        rate_km = Decimal(str(emp.sazba_km or 0))
        cestovne = (km_sum * rate_km).quantize(Decimal("0.01"))

        emp_oh = _as_dec(getattr(emp, "rezie_hod", 0) or 0, "0")
        celk_naklad_hod = (rate_h + emp_oh).quantize(Decimal("0.01"))
        celkem = (mzda + cestovne).quantize(Decimal("0.01"))

        employees_rows.append({
            "emp": emp,
            "plan_h": plan_h,
            "sazba_h": rate_h,
            "mzda": mzda,
            "km": km_sum,
            "sazba_km": rate_km,
            "cestovne": cestovne,
            "celkem": celkem,
            "celk_naklad_hod": celk_naklad_hod,
        })

    employees_total = sum((r["celkem"] for r in employees_rows), ZERO)

    # --- Externisté
    externist_rows = []
    for emp in Zamestnanec.objects.filter(is_active=True, typ_osoby=Zamestnanec.TYP_EXTERNAL):
        hrs = workh_by_emp.get(emp.id, ZERO)
        rate_h = _effective_rate_h(emp, first_day, calc_until)
        castka = (hrs * rate_h).quantize(Decimal("0.01"))

        km_sum = km_by_emp.get(emp.id, ZERO)
        rate_km = Decimal(str(emp.sazba_km or 0))
        cestovne = (km_sum * rate_km).quantize(Decimal("0.01"))

        emp_oh = _as_dec(getattr(emp, "rezie_hod", 0) or 0, "0")
        celk_naklad_hod = (rate_h + emp_oh).quantize(Decimal("0.01"))
        celkem = (castka + cestovne).quantize(Decimal("0.01"))

        externist_rows.append({
            "emp": emp,
            "hours": hrs,
            "rate_h": rate_h,
            "castka": castka,
            "km": km_sum,
            "rate_km": rate_km,
            "cestovne": cestovne,
            "celkem": celkem,
            "celk_naklad_hod": celk_naklad_hod,
        })

    externists_total = sum((r["celkem"] for r in externist_rows), ZERO)

    # --- Nové / uzavřené zakázky (jen do calc_until)
    new_projects = list(
        Zakazka.objects.filter(zakazka_start__date__gte=first_day, zakazka_start__date__lte=calc_until)
        .order_by("zakazka_start")
    )
    closed_projects = list(
        Zakazka.objects.filter(zakazka_konec_skut__date__gte=first_day, zakazka_konec_skut__date__lte=calc_until)
        .order_by("zakazka_konec_skut")
    )

    # --- Výkony po zakázkách (v období)
    projects_with_logs = (
        ZakazkaZamestnanec.objects
        .filter(den_prace__gte=first_day, den_prace__lte=calc_until)
        .values_list("zakazka_id", flat=True)
        .distinct()
    )

    all_logs_for_projects = (
        ZakazkaZamestnanec.objects
        .filter(zakazka_id__in=projects_with_logs)
        .select_related("zakazka", "zamestnanec", "zakazka__sazba")
        .order_by("zakazka_id", "den_prace", "cas_od", "cas_do")
    )

    # kapacity/sazby
    proj_caps: dict[int, Decimal] = {}
    proj_rates: dict[int, Decimal] = {}
    for z in Zakazka.objects.filter(id__in=projects_with_logs).select_related("sazba"):
        cap = _as_dec(getattr(z, "predpokladany_cas", 0), "0")
        proj_caps[z.id] = cap if cap is not None else ZERO
        proj_rates[z.id] = _as_dec(getattr(getattr(z, "sazba", None), "hodnota", 0), "0")

    cum_hours_by_proj: dict[int, Decimal] = defaultdict(lambda: ZERO)

    month_agg: dict[int, dict[int, dict]] = defaultdict(
        lambda: defaultdict(lambda: {"emp": None, "hours": ZERO, "naklady": ZERO, "vynosy": ZERO, "zisk": ZERO})
    )

    for v in all_logs_for_projects:
        proj_id = v.zakazka_id
        emp = v.zamestnanec
        h = _as_dec(_hours_between(v.den_prace, v.cas_od, v.cas_do), "0")
        if h <= ZERO:
            continue

        cap_total = proj_caps.get(proj_id, ZERO)
        proj_rate = proj_rates.get(proj_id, ZERO)

        rate_h = _effective_rate_h(emp, first_day, calc_until)
        emp_oh = _as_dec(getattr(emp, "rezie_hod", 0) or 0, "0")

        used_so_far = cum_hours_by_proj[proj_id]
        remaining = cap_total - used_so_far
        if remaining < ZERO:
            remaining = ZERO
        allowed = h if remaining >= h else (remaining if remaining > ZERO else ZERO)

        # ✅ DO TABULKY počítáme jen když log spadá do období
        if first_day <= v.den_prace <= calc_until:
            rev = (allowed * proj_rate)
            cost = (h * (rate_h + emp_oh))
            profit = (rev - cost)

            cell = month_agg[proj_id][emp.id]
            if cell["emp"] is None:
                cell["emp"] = emp
            cell["hours"] += h
            cell["vynosy"] += rev
            cell["naklady"] += cost
            cell["zisk"] += profit

        # ✅ cap kumulujeme vždy (i mimo období)
        cum_hours_by_proj[proj_id] = used_so_far + h

    month_tables: list[dict] = []
    if month_agg:
        z_map = {z.id: z for z in Zakazka.objects.filter(id__in=month_agg.keys()).select_related("klient")}
        for proj_id, rows in month_agg.items():
            z = z_map.get(proj_id)
            if not z:
                continue

            table_rows = []
            total_h = total_rev = total_cost = total_profit = ZERO
            for _emp_id, rec in rows.items():
                row = {
                    "emp": rec["emp"],
                    "hours": rec["hours"],
                    "vynosy": rec["vynosy"].quantize(Decimal("0.01")),
                    "naklady": rec["naklady"].quantize(Decimal("0.01")),
                    "zisk": rec["zisk"].quantize(Decimal("0.01")),
                }
                table_rows.append(row)
                total_h += rec["hours"]
                total_rev += row["vynosy"]
                total_cost += row["naklady"]
                total_profit += row["zisk"]

            table_rows.sort(key=lambda r: r["hours"], reverse=True)
            month_tables.append({
                "zakazka": z,
                "rows": table_rows,
                "total_hours": total_h,
                "total_vynosy": total_rev.quantize(Decimal("0.01")),
                "total_naklady": total_cost.quantize(Decimal("0.01")),
                "total_zisk": total_profit.quantize(Decimal("0.01")),
            })

        month_tables.sort(key=lambda t: getattr(t["zakazka"], "zakazka_cislo", "") or "")

    projects_total_zisk = sum(
        ((t.get("total_zisk") or ZERO) for t in month_tables),
        ZERO
    ).quantize(Decimal("0.01"))

    # --- výstup pro template
    return {
        "scope": scope,
        "ym": ym_for_template,
        "y": y_for_template,
        "prev_ym": prev_ym, "next_ym": next_ym,
        "prev_y": prev_y,   "next_y": next_y,

        "first_day": first_day,
        "last_day": last_day,
        "calc_until": calc_until,

        "employees_rows": employees_rows,
        "employees_total": employees_total,

        "externist_rows": externist_rows,
        "externists_total": externists_total,

        "new_projects": new_projects,
        "closed_projects": closed_projects,

        "projects_month_tables": month_tables,
        "projects_total_zisk": projects_total_zisk,

        "cache_source": "computed",

        # meta (volitelné)
        "snapshot_cutoff": cutoff,
    }