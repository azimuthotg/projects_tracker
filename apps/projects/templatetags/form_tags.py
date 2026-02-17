from django import template
from django.forms import CheckboxSelectMultiple

register = template.Library()


@register.filter
def is_checkbox_select(field):
    return isinstance(field.field.widget, CheckboxSelectMultiple)
