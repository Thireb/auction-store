from types import SimpleNamespace

import pytest

from apps.catalog import pricing
from apps.catalog.models import PriceTier
from apps.inventory import services

from .factories import VariantFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def cable():
    variant = VariantFactory(price=650, track_stock=False)
    PriceTier.objects.create(variant=variant, min_quantity=10, unit_price=550)
    PriceTier.objects.create(variant=variant, min_quantity=50, unit_price=480)
    PriceTier.objects.create(variant=variant, min_quantity=50, unit_price=420, wholesale_only=True)
    return variant


@pytest.mark.parametrize(
    ("qty", "wholesale", "price"),
    [(1, False, 650), (9, False, 650), (10, False, 550), (50, False, 480), (50, True, 420)],
)
def test_unit_price_uses_best_tier(cable, qty, wholesale, price):
    assert pricing.unit_price(cable, qty, wholesale) == price


def test_line_total(cable):
    assert pricing.line_total(cable, 10) == 5500


def test_public_buyers_do_not_see_wholesale_tiers(cable):
    assert [t.min_quantity for t in pricing.visible_tiers(cable)] == [10, 50]
    assert len(pricing.visible_tiers(cable, wholesale=True)) == 3


def test_quantity_rules():
    variant = VariantFactory(min_order_qty=12, order_step=6, track_stock=False)
    assert pricing.quantity_error(variant, 6) == "The minimum order for this item is 12."
    assert "steps of 6" in pricing.quantity_error(variant, 15)
    assert pricing.quantity_error(variant, 18) is None
    assert pricing.nearest_valid_quantity(variant, 5) == 12
    assert pricing.nearest_valid_quantity(variant, 20) == 18


def test_quantity_limited_by_stock():
    variant = VariantFactory()
    assert pricing.quantity_error(variant, 1) == "This item is sold out."
    services.receive(variant, 3)
    variant.refresh_from_db()
    assert pricing.quantity_error(variant, 4) == "Only 3 available."
    assert pricing.quantity_error(variant, 3) is None


def test_buyer_is_wholesale():
    assert not pricing.buyer_is_wholesale(None)
    assert not pricing.buyer_is_wholesale(SimpleNamespace())
    approved = SimpleNamespace(wholesale_profile=SimpleNamespace(is_approved=True))
    assert pricing.buyer_is_wholesale(approved)


def test_product_page_shows_public_tiers(client, cable):
    content = client.get(cable.product.get_absolute_url()).content.decode()
    assert '"min": 10' in content
    assert '"price": 420' not in content
