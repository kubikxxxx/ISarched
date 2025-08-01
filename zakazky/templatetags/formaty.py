from django import template

register = template.Library()

@register.filter
def format_cislo(value):
    try:
        number = float(value)
        return f"{int(round(number)):,}".replace(",", " ")
    except (ValueError, TypeError):
        return value

@register.filter
def attr(obj, attr_name):
    return getattr(obj, attr_name, '')