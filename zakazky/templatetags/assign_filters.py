from django import template

register = template.Library()

@register.filter
def get_subdodavka(assigned_list, subdodavka):
    return assigned_list.filter(subdodavka=subdodavka).first()