"""All stock changes go through these functions.

Each function locks the variant row, changes the numbers and writes a StockMovement.
Call them inside a transaction (ATOMIC_REQUESTS is on for views).
"""

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import F

from apps.catalog.models import Variant

from .models import StockItem, StockMovement
from .signals import stock_changed


class InsufficientStock(Exception):
    def __init__(self, variant, requested, available):
        self.variant, self.requested, self.available = variant, requested, available
        super().__init__(f"Only {max(available, 0)} of {variant} available, {requested} requested.")


def _lock(variant):
    return Variant.objects.select_for_update().select_related("product").get(pk=variant.pk)


def _log(variant, kind, quantity, *, lot=None, reference="", note="", user=None):
    StockMovement.objects.create(
        variant=variant,
        lot=lot,
        kind=kind,
        quantity=quantity,
        on_hand_after=variant.stock_on_hand,
        reserved_after=variant.stock_reserved,
        reference=reference,
        note=note,
        user=user if user and user.is_authenticated else None,
    )


def _check_positive(quantity):
    if quantity <= 0:
        raise ValueError("Quantity must be more than 0.")


def _after_change(variant):
    stock_changed.send(sender=Variant, variant=variant)


def _take_fifo(variant, quantity):
    """Remove `quantity` from the oldest lots first. Return [(lot, qty, cost_per_unit)]."""
    taken = []
    items = StockItem.objects.select_for_update().filter(variant=variant, quantity_on_hand__gt=0)
    for item in items.order_by("received_at", "pk"):
        if quantity == 0:
            break
        qty = min(item.quantity_on_hand, quantity)
        item.quantity_on_hand = F("quantity_on_hand") - qty
        item.save(update_fields=["quantity_on_hand"])
        taken.append((item.lot, qty, item.cost_per_unit))
        quantity -= qty
    if quantity:
        # Stock numbers on the variant and the lots disagree. Keep going, but record it.
        taken.append((None, quantity, None))
    return taken


@transaction.atomic
def receive(variant, quantity, *, lot=None, cost_per_unit=None, user=None, note=""):
    """Add new stock, for example from an auction lot."""
    _check_positive(quantity)
    variant = _lock(variant)
    item, _ = StockItem.objects.select_for_update().get_or_create(variant=variant, lot=lot)
    item.quantity_received += quantity
    item.quantity_on_hand += quantity
    if cost_per_unit is not None:
        item.cost_per_unit = cost_per_unit
    item.save()
    variant.stock_on_hand += quantity
    variant.save(update_fields=["stock_on_hand"])
    _log(variant, StockMovement.RECEIVED, quantity, lot=lot, note=note, user=user)
    _after_change(variant)
    return variant


@transaction.atomic
def reserve(variant, quantity, *, reference="", user=None):
    """Hold stock for a new order. Raise InsufficientStock if there is not enough."""
    _check_positive(quantity)
    variant = _lock(variant)
    if not variant.track_stock:
        return variant
    if variant.stock_available < quantity:
        raise InsufficientStock(variant, quantity, variant.stock_available)
    variant.stock_reserved += quantity
    variant.save(update_fields=["stock_reserved"])
    _log(variant, StockMovement.RESERVED, quantity, reference=reference, user=user)
    _after_change(variant)
    return variant


@transaction.atomic
def release(variant, quantity, *, reference="", user=None, note=""):
    """Give back a reservation, for example when an order is cancelled."""
    _check_positive(quantity)
    variant = _lock(variant)
    if not variant.track_stock:
        return variant
    quantity = min(quantity, variant.stock_reserved)
    if quantity:
        variant.stock_reserved -= quantity
        variant.save(update_fields=["stock_reserved"])
        _log(variant, StockMovement.RELEASED, -quantity, reference=reference, note=note, user=user)
        _after_change(variant)
    return variant


@transaction.atomic
def dispatch(variant, quantity, *, reference="", user=None):
    """Reserved stock leaves the warehouse. Return [(lot, qty, cost_per_unit)] for cost reports."""
    _check_positive(quantity)
    variant = _lock(variant)
    if not variant.track_stock:
        return []
    taken = _take_fifo(variant, quantity)
    variant.stock_reserved = max(variant.stock_reserved - quantity, 0)
    variant.stock_on_hand -= quantity
    variant.save(update_fields=["stock_reserved", "stock_on_hand"])
    for lot, qty, _cost in taken:
        _log(variant, StockMovement.DISPATCHED, -qty, lot=lot, reference=reference, user=user)
    _after_change(variant)
    return taken


@transaction.atomic
def return_to_stock(variant, quantity, *, lot=None, reference="", user=None, note=""):
    """Dispatched items came back (refused COD parcel) and are fit to sell again."""
    _check_positive(quantity)
    variant = _lock(variant)
    if not variant.track_stock:
        return variant
    item, _ = StockItem.objects.select_for_update().get_or_create(variant=variant, lot=lot)
    item.quantity_on_hand += quantity
    item.save(update_fields=["quantity_on_hand"])
    variant.stock_on_hand += quantity
    variant.save(update_fields=["stock_on_hand"])
    _log(
        variant,
        StockMovement.RETURNED,
        quantity,
        lot=lot,
        reference=reference,
        note=note,
        user=user,
    )
    _after_change(variant)
    return variant


@transaction.atomic
def adjust(variant, change, *, user, note):
    """Correct stock by hand (count, damage, loss). Needs the adjust_stock permission."""
    if not user.has_perm("inventory.adjust_stock"):
        raise PermissionDenied("You cannot adjust stock.")
    if not note:
        raise ValueError("Write a reason for the adjustment.")
    if change == 0:
        raise ValueError("The change cannot be 0.")
    variant = _lock(variant)
    if change > 0:
        item, _ = StockItem.objects.select_for_update().get_or_create(variant=variant, lot=None)
        item.quantity_on_hand += change
        item.save(update_fields=["quantity_on_hand"])
    else:
        if -change > variant.stock_on_hand:
            raise InsufficientStock(variant, -change, variant.stock_on_hand)
        _take_fifo(variant, -change)
    variant.stock_on_hand += change
    variant.save(update_fields=["stock_on_hand"])
    _log(variant, StockMovement.ADJUSTMENT, change, note=note, user=user)
    _after_change(variant)
    return variant
