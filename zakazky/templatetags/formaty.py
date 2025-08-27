from datetime import datetime
from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()

@register.filter
def format_cislo(value):
    """
    Celé číslo s mezerami jako oddělovači tisíců.
    """
    try:
        number = float(value)
        return f"{int(round(number)):,}".replace(",", " ")
    except (ValueError, TypeError):
        return value

@register.filter
def format_cislo2(value, places=2):
    """
    Číslo s oddělovačem tisíců (mezera) a desetinnou ČÁRKOU.
    Použití: {{ hodnota|format_cislo2 }} nebo {{ hodnota|format_cislo2:0 }}.
    """
    try:
        places = int(places)
        num = Decimal(str(value))
        q = Decimal(10) ** -places
        num = num.quantize(q)
        s = f"{num:,.{places}f}"          # 1,234,567.89
        s = s.replace(",", " ").replace(".", ",")  # 1 234 567,89
        return s
    except (InvalidOperation, ValueError, TypeError):
        return value

@register.filter
def attr(obj, attr_name):
    return getattr(obj, attr_name, '')

@register.filter
def hodiny_hhmm(value):
    """
    1.5 -> '01:30', -2.25 -> '-02:15'
    """
    try:
        total_minutes = int(round(float(value) * 60))
    except (TypeError, ValueError):
        return value
    sign = "-" if total_minutes < 0 else ""
    total_minutes = abs(total_minutes)
    h = total_minutes // 60
    m = total_minutes % 60
    return f"{sign}{h:02d}:{m:02d}"

@register.filter
def trvani_hodin(vykaz):
    """
    Vrátí trvání výkazu v hodinách (float), aby se dalo řetězit s |hodiny_hhmm.
    Pokud nejsou časy, vrací 0.
    """
    try:
        if not (vykaz and vykaz.den_prace and vykaz.cas_od and vykaz.cas_do):
            return 0.0
        start = datetime.combine(vykaz.den_prace, vykaz.cas_od)
        end = datetime.combine(vykaz.den_prace, vykaz.cas_do)
        delta = end - start
        secs = max(delta.total_seconds(), 0)
        return secs / 3600.0
    except Exception:
        return 0.0