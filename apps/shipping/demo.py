"""Demo delivery settings. Used by `manage.py seed_demo`."""

from apps.catalog.models import ADVANCE_PERCENT, Category

from .cities import load_cities
from .models import City, ShippingSettings


def seed_shipping(stdout=None):
    load_cities()
    settings = ShippingSettings.load()
    if not settings.advance_payment_details:
        settings.default_delivery_fee = 250
        settings.default_cod_fee = 0
        settings.free_delivery_above = 15000
        settings.bulky_item_fee = 2500
        settings.advance_above_total = 100000
        settings.advance_percent_above_total = 10
        settings.advance_payment_details = (
            "Demo Bank - Account title: Auction Store - IBAN: PK00DEMO0000000000000000\n"
            "Easypaisa / JazzCash: 0300 0000000 (Auction Store)"
        )
        settings.save()
    City.objects.filter(
        province__in=["gb", "ajk", "balochistan"], delivery_fee__isnull=True
    ).update(delivery_fee=450)
    Category.objects.filter(name="Furniture", parent=None).update(
        is_bulky=True, advance_type=ADVANCE_PERCENT, advance_value=20
    )
    if stdout:
        stdout.write("Shipping: cities, fees and furniture advance rule set.")
