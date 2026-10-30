from decimal import Decimal

import pytest
from django.urls import reverse

from apps.core.templatetags.money import rupees


@pytest.mark.parametrize(
    ("value", "expected"),
    [(1250, "Rs 1,250"), (Decimal("1999.60"), "Rs 2,000"), (0, "Rs 0"), (None, ""), ("abc", "abc")],
)
def test_rupees(value, expected):
    assert rupees(value) == expected


@pytest.mark.django_db
def test_home_uses_base_template(client, settings):
    settings.STORE_NAME = "Test Store"
    response = client.get(reverse("core:home"))
    content = response.content.decode()
    assert "htmx.org@2.0.4" in content
    assert "alpinejs@3.14.9" in content
    assert "Test Store" in content
    assert 'id="cart-count"' in content
