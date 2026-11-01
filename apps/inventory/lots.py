"""Public lots in the store: item counts, the current lot, the next lot and a lot's products.

A product belongs to every lot it has stock in (StockItem). Counts are products, not units,
because most products are one-off pieces: "31 of 46 items still here".
"""

from django.db.models import Count, F
from django.utils import timezone

from apps.catalog.models import Product

from .models import Lot, StockItem

# Quick filters on a lot page: key -> (label, filter function).
UNDER_PRICE = 5000
LIKE_NEW = ["new", "open_box", "used_like_new"]
CHIPS = {
    "all": "Everything",
    "under": f"Under Rs {UNDER_PRICE:,}",
    "like": "New or like new",
    "bulk": "Cheaper in bulk",
}


def newest_first(lots):
    return lots.order_by(
        F("opens_at").desc(nulls_last=True), F("purchase_date").desc(nulls_last=True), "-pk"
    )


def product_ids(lot):
    """A subquery of the ids of products with stock in `lot`."""
    return StockItem.objects.filter(lot=lot).values("variant__product")


def attach_counts(lots):
    """Set items_total, items_left, items_sold and left_percent on each lot. 2 queries."""
    lots = list(lots)
    if not lots:
        return lots
    totals = dict(
        Lot.objects.filter(pk__in=[lot.pk for lot in lots])
        .annotate(n=Count("stock_items__variant__product", distinct=True))
        .values_list("pk", "n")
    )
    left = dict(
        Product.objects.listed()
        .filter(variants__stock_items__lot__in=lots)
        .values_list("variants__stock_items__lot")
        .annotate(n=Count("pk", distinct=True))
    )
    for lot in lots:
        lot.items_total = totals.get(lot.pk, 0)
        lot.items_left = left.get(lot.pk, 0) if lot.is_open else lot.items_total
        lot.items_sold = max(lot.items_total - lot.items_left, 0)
        lot.left_percent = round(100 * lot.items_left / lot.items_total) if lot.items_total else 0
    return lots


def current_lot():
    """The newest open public lot that still has items, with counts. None if there is none."""
    candidates = attach_counts(newest_first(Lot.objects.public().open())[:6])
    return next((lot for lot in candidates if lot.items_left), None)


def next_lot():
    """The public lot that opens soonest, with counts."""
    lot = Lot.objects.public().upcoming().order_by("opens_at").first()
    return attach_counts([lot])[0] if lot else None


def lot_for_product(product):
    """The open public lot to show on a product page, or None."""
    return (
        newest_first(
            Lot.objects.public().open().filter(stock_items__variant__product=product).distinct()
        )
        .only("reference", "slug", "public_title", "source", "opens_at")
        .first()
    )


def lot_products(products, lot):
    """`products` (a product queryset) that have stock in `lot`."""
    return products.filter(pk__in=product_ids(lot))


def apply_chip(products, key):
    if key == "under":
        return products.filter(variants__is_active=True, variants__price__lt=UNDER_PRICE).distinct()
    if key == "like":
        return products.filter(condition__in=LIKE_NEW)
    if key == "bulk":
        return products.filter(
            variants__is_active=True,
            variants__price_tiers__isnull=False,
            variants__price_tiers__wholesale_only=False,
        ).distinct()
    return products


def chip_list(active):
    return [(key, label, key == active) for key, label in CHIPS.items()]


def sold_in_lot(lot, limit=6):
    return lot_products(Product.objects.recently_sold(), lot).prefetch_related("images")[:limit]


def past_lots(limit=12):
    """Public lots that opened and have nothing left."""
    lots = attach_counts(newest_first(Lot.objects.public().open())[:40])
    return [lot for lot in lots if lot.items_total and not lot.items_left][:limit]


def open_lots():
    lots = attach_counts(newest_first(Lot.objects.public().open())[:40])
    return [lot for lot in lots if lot.items_left]


def upcoming_lots():
    return attach_counts(Lot.objects.public().upcoming().order_by("opens_at")[:6])


def seconds_until(moment):
    return max(int((moment - timezone.now()).total_seconds()), 0) if moment else 0
