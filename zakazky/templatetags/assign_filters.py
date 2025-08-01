from django import template

register = template.Library()

@register.filter
def get_subdodavka(assigned_list, subdodavka):
    return assigned_list.filter(subdodavka=subdodavka).first()

@register.filter(name='add_class')
def add_class(value, css_class):
    return value.as_widget(attrs={"class": css_class})

@register.filter
def getattribute(obj, attr):
    return getattr(obj, attr, None)