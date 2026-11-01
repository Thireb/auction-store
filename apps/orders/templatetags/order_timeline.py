from django import template

from .. import timeline

register = template.Library()


@register.simple_tag
def order_steps(order):
    return timeline.steps(order)
