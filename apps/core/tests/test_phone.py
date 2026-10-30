import pytest
from django.core.exceptions import ValidationError

from apps.core.phone import display_pk_mobile, normalize_pk_mobile


@pytest.mark.parametrize(
    "raw",
    [
        "03001234567",
        "0300-1234567",
        "3001234567",
        "+92 300 1234567",
        "0092 300 1234567",
        "923001234567",
    ],
)
def test_normalize(raw):
    assert normalize_pk_mobile(raw) == "+923001234567"


@pytest.mark.parametrize("raw", ["", "0423456789", "0300123456", "abc", "+1 300 1234567"])
def test_invalid(raw):
    with pytest.raises(ValidationError):
        normalize_pk_mobile(raw)


def test_display():
    assert display_pk_mobile("+923001234567") == "0300 1234567"
