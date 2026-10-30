from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def rupees(value):
    """Format a number as Pakistani rupees: 1250 -> "Rs 1,250". Paisa are not shown."""
    if value is None or value == "":
        return ""
    try:
        amount = Decimal(value).quantize(Decimal("1"))
    except (InvalidOperation, TypeError, ValueError):
        return value
    return f"Rs {amount:,}"
