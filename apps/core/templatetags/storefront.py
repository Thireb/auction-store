from django import template
from django.utils.timesince import timesince

register = template.Library()


@register.filter
def ago(value):
    """ "3 hours" for a time 3 hours and 10 minutes ago: the largest unit only."""
    return timesince(value, depth=1) if value else ""
