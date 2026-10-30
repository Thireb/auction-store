"""Demo stock, lots and bulk prices. Used by `manage.py seed_demo`."""

import datetime
from decimal import Decimal

from apps.catalog.models import PriceTier, Variant

from . import services
from .models import Lot

ONE_OFF_CATEGORIES = {"Furniture", "Decor"}
BULK_CATEGORIES = {"Chargers", "Cables", "Phone cases", "Earbuds"}
SOLD_OUT_SKU = "DEMO-001-0"  # Leave 1 product without stock, to show the "Sold" badge.


def seed_inventory(stdout=None):
    lot, created = Lot.objects.get_or_create(
        reference="DXB-DEMO-01",
        defaults={
            "source": "Demo auction house, Dubai",
            "purchase_date": datetime.date(2026, 9, 15),
            "total_cost": 1_500_000,
            "landed_cost": 250_000,
        },
    )
    if not created:
        return
    for variant in Variant.objects.select_related("product__category__parent"):
        if variant.sku == SOLD_OUT_SKU:
            continue
        category = variant.product.category
        names = {category.name, category.parent.name if category.parent else ""}
        if names & BULK_CATEGORIES:
            quantity = 200
            price = variant.price
            PriceTier.objects.create(
                variant=variant, min_quantity=10, unit_price=round(price * Decimal("0.85"))
            )
            PriceTier.objects.create(
                variant=variant, min_quantity=50, unit_price=round(price * Decimal("0.75"))
            )
            PriceTier.objects.create(
                variant=variant,
                min_quantity=100,
                unit_price=round(price * Decimal("0.65")),
                wholesale_only=True,
            )
            if category.name == "Phone cases":
                variant.min_order_qty, variant.order_step = 5, 5
                variant.save(update_fields=["min_order_qty", "order_step"])
        elif names & ONE_OFF_CATEGORIES:
            quantity = 1
        else:
            quantity = 6
        services.receive(
            variant, quantity, lot=lot, cost_per_unit=round(variant.price * Decimal("0.55"))
        )
    if stdout:
        stdout.write("Inventory: demo lot received, bulk tiers added.")
