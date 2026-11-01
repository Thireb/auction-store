"""Demo stock, lots and bulk prices. Used by `manage.py seed_demo`."""

import datetime
import random
from decimal import Decimal

from django.utils import timezone

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


# Public face of each lot: title, story, days until it opens (None: open now).
LOT_STORIES = {
    "DXB-DEMO-01": (
        "Dubai hotel refit auction",
        "A 5-star hotel in Dubai Marina replaced its rooms and lobby. We bought sofas, "
        "tables and lamps at the auction. Each piece is checked and photographed here.",
        None,
    ),
    "DXB-DEMO-02": (
        "Emirates electronics auction",
        "Boxes of chargers, cables and watches from an electronics importer in Dubai. "
        "Most are new or open box.",
        None,
    ),
    "SHJ-DEMO-03": (
        "Sharjah export leftovers",
        "Shoes and decor that a Sharjah exporter could not ship. New, in mixed sizes.",
        None,
    ),
    "KHI-DEMO-04": (
        "Karachi export surplus",
        "The next shipment. You see the pieces the moment it opens.",
        3,
    ),
}


def _make_public(lot):
    title, story, days = LOT_STORIES.get(lot.reference, ("", "", None))
    if lot.is_public or not title:
        return
    lot.is_public, lot.public_title, lot.story = True, title, story
    if days is not None:
        opens = timezone.localtime() + datetime.timedelta(days=days)
        lot.opens_at = opens.replace(hour=20, minute=0, second=0, microsecond=0)
    lot.save()


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
    for lot in lots:
        _make_public(lot)
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


# Items that arrive before their photos, and the tray photos waiting for them.
# lot -> [(title, category, price, condition)]
TRAY_ITEMS = {
    "DXB-DEMO-01": [
        ("Rattan side chair", "Chairs", 12500, "used_like_new"),
        ("Brass floor lamp", "Lamps", 9800, "used_good"),
    ],
    "DXB-DEMO-02": [
        ("Wireless earbuds, sealed box", "Earbuds", 4200, "new"),
        ("Steel analog watch", "Analog watches", 15500, "open_box"),
    ],
    "SHJ-DEMO-03": [
        ("Canvas sneakers, EU 41", "Sneakers", 5200, "new"),
        ("Ceramic vase set of 3", "Vases", 6400, "new"),
    ],
}


def _photo_file(text, seed, name):
    from apps.catalog.demo import placeholder_image

    image = placeholder_image(text, seed, name)
    image.name = name
    return image


def seed_photo_trays(stdout=None):
    """Items without photos and a tray of photos for each open demo lot. Skips a filled tray."""
    from apps.catalog.models import Category, Product

    from . import photos

    added = 0
    for lot_n, (reference, items) in enumerate(TRAY_ITEMS.items()):
        lot = Lot.objects.filter(reference=reference).first()
        if lot is None or lot.photos.exists():
            continue
        shot = 1
        for item_n, (title, category_name, price, condition) in enumerate(items):
            category = Category.objects.filter(name=category_name).first()
            if category is None:
                continue
            product, created = Product.objects.get_or_create(
                title=title,
                defaults={
                    "category": category,
                    "condition": condition,
                    "origin_note": f"{lot.title}, demo lot",
                },
            )
            if created:
                variant = Variant.objects.create(
                    product=product, sku=f"DEMO-NP-{lot_n}{item_n}", price=price
                )
                services.receive(variant, 1, lot=lot, cost_per_unit=round(price * 0.5))
            for view in ("front", "side"):
                name = f"IMG_{lot_n + 1}{shot:03d}.jpg"
                photos.add_photo(
                    lot, _photo_file(f"{title}, {view}", lot_n * 100 + shot, name), None
                )
                shot += 1
                added += 1
        blurry = photos.add_photo(
            lot, _photo_file("Blurry shot", lot_n * 100 + 99, f"IMG_{lot_n + 1}099.jpg"), None
        )
        photos.mark_not_usable(blurry, None)
        added += 1
    if stdout:
        stdout.write(f"Photo trays: {added} demo tray photos, items waiting for photos.")
