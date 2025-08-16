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