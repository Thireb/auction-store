"""Order status changes. Every change goes through `transition`, which also moves stock."""

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from apps.inventory import services as stock

from .models import Order, OrderStatusHistory

S = Order  # Short name for the status table below.
ALLOWED = {
    S.PENDING: [S.AWAITING_ADVANCE, S.CONFIRMED, S.CANCELLED],
    S.AWAITING_ADVANCE: [S.CONFIRMED, S.CANCELLED],
    S.CONFIRMED: [S.PACKED, S.SHIPPED, S.CANCELLED],
    S.PACKED: [S.SHIPPED, S.CANCELLED],
    S.SHIPPED: [S.DELIVERED, S.RETURNED],
    S.DELIVERED: [S.COMPLETED, S.RETURNED],
    S.COMPLETED: [],
    S.CANCELLED: [],
    S.RETURNED: [],
}
RESERVED_STATUSES = {S.PENDING, S.AWAITING_ADVANCE, S.CONFIRMED, S.PACKED}
STAFF_CONFIRMED = {S.CONFIRMED, S.PACKED}


class TransitionError(Exception):
    pass


def allowed_transitions(order, user=None):
    targets = list(ALLOWED[order.status])
    if order.advance_status != Order.ADVANCE_PENDING and S.AWAITING_ADVANCE in targets:
        targets.remove(S.AWAITING_ADVANCE)
    if user is not None:
        targets = [t for t in targets if _has_permission(order, t, user)]
    return targets


def _has_permission(order, target, user):
    if not user.has_perm("orders.change_order"):
        return False
    if target == S.CANCELLED and order.status in STAFF_CONFIRMED:
        return user.has_perm("orders.cancel_confirmed_order")
    return True


@transaction.atomic
def transition(order, target, *, user, note="", courier="", tracking_number=""):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if target not in ALLOWED[order.status]:
        raise TransitionError(
            f"An order cannot go from {order.get_status_display()} to "
            f"{dict(Order.STATUS_CHOICES)[target]}."
        )
    if not _has_permission(order, target, user):
        raise PermissionDenied("You do not have permission for this change.")
    if target == S.CONFIRMED and order.advance_status == Order.ADVANCE_PENDING:
        raise TransitionError("Mark the advance as received before you confirm this order.")
    if target == S.AWAITING_ADVANCE and order.advance_status != Order.ADVANCE_PENDING:
        raise TransitionError("This order does not need an advance.")
    if target == S.SHIPPED and not courier:
        raise TransitionError("Enter the courier for a shipped order.")

    previous = order.status
    items = list(order.items.select_related("variant"))
    if target == S.CANCELLED and previous in RESERVED_STATUSES:
        for item in items:
            if item.variant:
                stock.release(item.variant, item.quantity, reference=order.number, user=user)
    elif target == S.SHIPPED:
        for item in items:
            if item.variant:
                taken = stock.dispatch(
                    item.variant, item.quantity, reference=order.number, user=user
                )
                item.cost_total = sum((cost or 0) * qty for _lot, qty, cost in taken)
                item.save(update_fields=["cost_total"])
        order.shipments.create(courier=courier, tracking_number=tracking_number)
    elif target == S.RETURNED:
        for item in items:
            if item.variant:
                stock.return_to_stock(
                    item.variant, item.quantity, reference=order.number, user=user, note=note
                )

    order.status = target
    stamp = {S.CONFIRMED: "confirmed_at", S.SHIPPED: "shipped_at", S.DELIVERED: "delivered_at"}
    fields = ["status", "updated_at"]
    if target in stamp:
        setattr(order, stamp[target], timezone.now())
        fields.append(stamp[target])
    order.save(update_fields=fields)
    OrderStatusHistory.objects.create(
        order=order, from_status=previous, to_status=target, user=user, note=note
    )
    return order


@transaction.atomic
def mark_advance_received(order, *, user, note=""):
    if not user.has_perm("orders.change_order"):
        raise PermissionDenied
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.advance_status != Order.ADVANCE_PENDING:
        raise TransitionError("This order has no pending advance.")
    order.advance_status = Order.ADVANCE_RECEIVED
    order.save(update_fields=["advance_status", "updated_at"])
    OrderStatusHistory.objects.create(
        order=order,
        from_status=order.status,
        to_status=order.status,
        user=user,
        note=f"Advance of Rs {order.advance_amount:,} received. {note}".strip(),
    )
    return order
