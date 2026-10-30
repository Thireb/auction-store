import re

from django.core.exceptions import ValidationError

MOBILE = re.compile(r"^3\d{9}$")


def normalize_pk_mobile(value):
    """Return a Pakistani mobile number as +923XXXXXXXXX, or raise ValidationError.

    Accepts 03001234567, 0300-1234567, 3001234567, +92 300 1234567 and 0092...
    """
    digits = re.sub(r"\D", "", value or "")
    if digits.startswith("0092"):
        digits = digits[4:]
    elif digits.startswith("92") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0"):
        digits = digits[1:]
    if not MOBILE.match(digits):
        raise ValidationError("Enter a Pakistani mobile number, for example 0300 1234567.")
    return f"+92{digits}"


def display_pk_mobile(value):
    """+923001234567 -> 0300 1234567"""
    if value and value.startswith("+92") and len(value) == 13:
        return f"0{value[3:6]} {value[6:]}"
    return value
