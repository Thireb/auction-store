"""The order progress that customers see on the thank-you, tracking and account pages."""

from django.template.defaultfilters import date as format_date

from apps.core.templatetags.money import rupees

from .models import Order

# How far an order has come: 0 placed, 1 confirmed, 2 packed, 3 shipped, 4 delivered.
RANK = {
    Order.PENDING: 0,
    Order.AWAITING_ADVANCE: 0,
    Order.CONFIRMED: 1,
    Order.PACKED: 2,
    Order.SHIPPED: 3,
    Order.DELIVERED: 4,
    Order.COMPLETED: 4,
    Order.CANCELLED: 0,
    Order.RETURNED: 3,
}


def steps(order):
    """A list of dicts: title, detail and state ("done", "now", "todo" or "stopped")."""
    shipment = order.shipments.all()[0] if order.shipments.all() else None
    waiting_for_advance = order.status == Order.AWAITING_ADVANCE
    rows = [
        ("Order placed", format_date(order.created_at, "j F, g:i A")),
        (
            "We check your advance payment" if waiting_for_advance else "We call you to confirm",
            "Keep your phone near you" if order.status == Order.PENDING else "",
        ),
        ("Packed", ""),
        (
            "With the courier",
            f"{shipment.courier}, tracking number {shipment.tracking_number}"
            if shipment and shipment.tracking_number
            else "You get a tracking number",
        ),
        ("Delivered, you pay cash", f"Pay the rider {rupees(order.balance_after_advance)}"),
    ]
    rank = RANK.get(order.status, 0)
    stopped = order.status in (Order.CANCELLED, Order.RETURNED)
    result = []
    for i, (title, detail) in enumerate(rows):
        if i <= rank:
            state = "done"
        elif stopped:
            break
        else:
            state = "now" if i == rank + 1 else "todo"
        result.append({"title": title, "detail": detail, "state": state})
    if stopped:
        result.append({"title": order.get_status_display(), "detail": "", "state": "stopped"})
    return result
