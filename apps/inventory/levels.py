"""Stock levels for staff: near empty and out of stock.

A variant is near empty when 1 or more pieces are left, but not more than its own
"near empty at" number, or the store default when the variant has none.
"""

from django.db.models import F, Q, Value
from django.db.models.functions import Coalesce

from apps.catalog.models import Variant
from apps.shipping.models import ShippingSettings


def default_level():
    return ShippingSettings.load().low_stock_default


def with_levels(variants=None):
    """Add `available` and `low_at` to each variant."""
    variants = Variant.objects.all() if variants is None else variants
    return variants.annotate(
        available=F("stock_on_hand") - F("stock_reserved"),
        low_at=Coalesce("low_stock_threshold", Value(default_level())),
    )


def near_empty(variants=None):
    return with_levels(variants).filter(
        is_active=True, track_stock=True, available__gt=0, available__lte=F("low_at")
    )


def out_of_stock(variants=None):
    return with_levels(variants).filter(is_active=True, track_stock=True, available__lte=0)


def in_stock(variants=None):
    return with_levels(variants).filter(Q(track_stock=False) | Q(available__gt=0))
