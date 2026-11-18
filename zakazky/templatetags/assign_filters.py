from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()

@register.filter
def get_subdodavka(assigned, subdodavka):
    """Podporuje QuerySet, dict[id -> row] i list objektů s subdodavka / subdodavka_id."""
    if assigned is None:
        return None
    if isinstance(assigned, dict):
        return assigned.get(subdodavka.id) or assigned.get(str(subdodavka.id))
    if hasattr(assigned, "filter"):
        return assigned.filter(subdodavka=subdodavka).first()
    for item in assigned:
        sid = getattr(item, "subdodavka_id", None)
        if sid is None:
            sub = getattr(item, "subdodavka", None)
            sid = getattr(sub, "id", None)
        if sid == subdodavka.id:
            return item
    return None

@register.filter(name='add_class')
def add_class(value, css_class):
    return value.as_widget(attrs={"class": css_class})

@register.filter
def getattribute(obj, attr):
    return getattr(obj, attr, None)

@register.filter
def get_item(mapping, key):
    if not mapping:
        return None
    if key in mapping:
        return mapping[key]
    skey = str(key)
    if skey in mapping:
        return mapping[skey]
    try:
        ikey = int(key)
    except (TypeError, ValueError):
        return None
    return mapping.get(ikey)
