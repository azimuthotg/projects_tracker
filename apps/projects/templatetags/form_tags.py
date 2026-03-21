from django import template
from django.forms import CheckboxSelectMultiple

register = template.Library()


@register.filter
def is_checkbox_select(field):
    return isinstance(field.field.widget, CheckboxSelectMultiple)


_THAI_MONTHS = [
    '', 'มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน',
    'พฤษภาคม', 'มิถุนายน', 'กรกฎาคม', 'สิงหาคม',
    'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม',
]


@register.filter
def thaidate(value):
    """Format date as Thai: D เดือน YYYY+543  e.g. 1 กุมภาพันธ์ 2568"""
    if not value:
        return ''
    try:
        return f"{value.day} {_THAI_MONTHS[value.month]} {value.year + 543}"
    except (AttributeError, TypeError, IndexError):
        return value


_THAI_MONTHS_SHORT = [
    '', 'ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.',
    'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.',
    'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.',
]


@register.filter
def thaidate_short(value):
    """Format date as short Thai: D ม.ค. 68  e.g. 1 ก.พ. 68"""
    if not value:
        return ''
    try:
        return f"{value.day} {_THAI_MONTHS_SHORT[value.month]} {str(value.year + 543)[2:]}"
    except (AttributeError, TypeError, IndexError):
        return value


@register.filter
def thaidate_time(value):
    """Format datetime as Thai with time: D เดือน YYYY+543 HH:MM"""
    if not value:
        return ''
    try:
        return f"{value.day} {_THAI_MONTHS[value.month]} {value.year + 543} {value.hour:02d}:{value.minute:02d}"
    except (AttributeError, TypeError, IndexError):
        return value
