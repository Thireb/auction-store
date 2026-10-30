"""Numbers for the portal dashboard."""

from django.db.models import Count, Sum
from django.utils import timezone

from apps.accounts.models import WholesaleProfile
from apps.inventory import levels
from apps.orders.models import Order, OrderItem


def _sum(queryset, field):
    return queryset.aggregate(value=Sum(field))["value"] or 0


def dashboard_numbers(user):
    now = timezone.localtime()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month = today.replace(day=1)
    orders = Order.objects.all()
    live = orders.exclude(status__in=[Order.CANCELLED, Order.RETURNED])
    by_status = dict(orders.values_list("status").annotate(n=Count("pk")))
    delivered = orders.filter(status=Order.DELIVERED)
    cod_pending = _sum(delivered, "total") - _sum(
        delivered.filter(advance_status=Order.ADVANCE_RECEIVED), "advance_amount"
    )
    numbers = {
        "orders_today": live.filter(created_at__gte=today).count(),
        "sales_today": _sum(live.filter(created_at__gte=today), "total"),
        "sales_month": _sum(live.filter(created_at__gte=month), "total"),
        "to_confirm": by_status.get(Order.PENDING, 0),
        "awaiting_advance": by_status.get(Order.AWAITING_ADVANCE, 0),
        "advance_proofs": orders.filter(advance_status=Order.ADVANCE_PENDING)
        .exclude(advance_proof="")
        .count(),
        "to_dispatch": by_status.get(Order.CONFIRMED, 0) + by_status.get(Order.PACKED, 0),
        "in_transit": by_status.get(Order.SHIPPED, 0),
        "cod_pending": cod_pending,
        "returned_month": orders.filter(status=Order.RETURNED, updated_at__gte=month).count(),
        "low_stock": levels.near_empty().count(),
        "out_of_stock": levels.out_of_stock().count(),
        "wholesale_pending": WholesaleProfile.objects.filter(
            status=WholesaleProfile.PENDING
        ).count(),
    }
    if user.has_perm("inventory.view_cost_and_profit"):
        shipped = OrderItem.objects.filter(
            order__shipped_at__gte=month, cost_total__isnull=False
        ).exclude(order__status=Order.RETURNED)
        numbers["profit_month"] = _sum(shipped, "line_total") - _sum(shipped, "cost_total")
    return numbers
