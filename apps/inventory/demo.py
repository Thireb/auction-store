"""Demo stock, lots and bulk prices. Used by `manage.py seed_demo`."""

import datetime
import random
from decimal import Decimal

from apps.catalog.demo_extra import EXTRA_BULK
from apps.catalog.models import PriceTier, Variant

from . import services
from .models import Lot

ONE_OFF_CATEGORIES = {"Furniture", "Decor"}
BULK_CATEGORIES = {"Chargers", "Cables", "Phone cases", "Earbuds", *EXTRA_BULK}
SOLD_OUT_SKU = "DEMO-001-0"  # Leave 1 product without stock, to show the "Sold" badge.

LOTS = [
    # reference, source, purchase date, total cost, landed cost
    ("DXB-DEMO-01", "Demo auction house, Dubai", datetime.date(2026, 9, 15), 1_500_000, 250_000),
    ("DXB-DEMO-02", "Emirates auction, Dubai", datetime.date(2026, 9, 28), 2_400_000, 380_000),
    ("SHJ-DEMO-03", "Export leftovers, Sharjah", datetime.date(2026, 10, 6), 1_800_000, 290_000),
    ("KHI-DEMO-04", "Export surplus, Karachi", datetime.date(2026, 10, 20), 950_000, 60_000),
]


def _add_tiers(variant):
    price = variant.price
    for min_quantity, factor, wholesale_only in [
        (10, "0.85", False),
        (50, "0.75", False),
        (100, "0.65", True),
    ]:
        PriceTier.objects.create(
            variant=variant,
            min_quantity=min_quantity,
            unit_price=round(price * Decimal(factor)),
            wholesale_only=wholesale_only,
        )


def seed_inventory(stdout=None):
    lots = [
        Lot.objects.get_or_create(
            reference=ref,
            defaults={
                "source": source,
                "purchase_date": date,
                "total_cost": total,
                "landed_cost": landed,
            },
        )[0]
        for ref, source, date, total, landed in LOTS
    ]
    rng = random.Random(7)
    received = 0
    # Only variants with no stock yet, so the seed can run again after new products.
    variants = (
        Variant.objects.filter(stock_items__isnull=True)
        .exclude(sku=SOLD_OUT_SKU)
        .select_related("product__category__parent")
        .order_by("pk")
    )
    for variant in variants:
        category = variant.product.category
        names = {category.name, category.parent.name if category.parent else ""}
        if names & BULK_CATEGORIES:
            quantity = rng.choice([150, 200, 300, 500])
            if not variant.price_tiers.exists():
                _add_tiers(variant)
            if category.name in {"Phone cases", "Screen protectors"}:
                variant.min_order_qty, variant.order_step = 5, 5
                variant.save(update_fields=["min_order_qty", "order_step"])
        elif names & ONE_OFF_CATEGORIES:
            quantity = rng.choice([1, 1, 1, 2])
        else:
            quantity = rng.randint(2, 15)
        services.receive(
            variant,
            quantity,
            lot=lots[variant.pk % len(lots)],
            cost_per_unit=round(variant.price * Decimal(rng.choice(["0.45", "0.55", "0.6"]))),
        )
        received += 1
    if stdout:
        stdout.write(f"Inventory: {len(lots)} lots, stock for {received} variants, bulk tiers.")
