"""The owner dashboard and the staff activity page in the admin."""

from datetime import timedelta

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db.models import Count, F, Q, Sum
from django.template.response import TemplateResponse
from django.urls import path
from django.utils import timezone
from simple_history.models import registered_models

from apps.catalog.models import Variant
from apps.inventory.models import StockMovement
from apps.orders.models import Order, OrderItem, OrderStatusHistory


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
    tracked = Variant.objects.filter(is_active=True, track_stock=True).annotate(
        available=F("stock_on_hand") - F("stock_reserved")
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
        "low_stock": tracked.filter(
            available__gt=0, available__lte=F("low_stock_threshold")
        ).count(),
        "out_of_stock": tracked.filter(available__lte=0).count(),
    }
    if user.has_perm("inventory.view_cost_and_profit"):
        shipped = OrderItem.objects.filter(
            order__shipped_at__gte=month, cost_total__isnull=False
        ).exclude(order__status=Order.RETURNED)
        numbers["profit_month"] = _sum(shipped, "line_total") - _sum(shipped, "cost_total")
    return numbers


def dashboard_view(request):
    if not request.user.has_perm("orders.view_order"):
        raise PermissionDenied
    context = {
        **admin.site.each_context(request),
        "title": "Dashboard",
        "n": dashboard_numbers(request.user),
    }
    return TemplateResponse(request, "admin/dashboard.html", context)


def _activity(user_id=None, days=7, limit=300):
    since = timezone.now() - timedelta(days=days)
    rows = []
    for model in registered_models.values():
        if model._meta.app_label not in {"catalog", "inventory", "orders", "shipping"}:
            continue
        history = model.history.filter(history_date__gte=since, history_user__isnull=False)
        if user_id:
            history = history.filter(history_user_id=user_id)
        for record in history.select_related("history_user").order_by("-history_date")[:limit]:
            changes = ""
            if record.history_type == "~" and record.prev_record:
                delta = record.diff_against(record.prev_record)
                changes = "; ".join(f"{c.field}: {c.old} -> {c.new}" for c in delta.changes)
            rows.append(
                {
                    "when": record.history_date,
                    "user": record.history_user,
                    "what": f"{model._meta.verbose_name}: {record}",
                    "action": {"+": "Created", "~": "Changed", "-": "Deleted"}[record.history_type],
                    "details": changes,
                }
            )
    movements = StockMovement.objects.filter(created_at__gte=since, user__isnull=False)
    statuses = OrderStatusHistory.objects.filter(created_at__gte=since, user__isnull=False)
    if user_id:
        movements, statuses = movements.filter(user_id=user_id), statuses.filter(user_id=user_id)
    for m in movements.select_related("user", "variant__product")[:limit]:
        rows.append(
            {
                "when": m.created_at,
                "user": m.user,
                "what": f"stock: {m.variant}",
                "action": m.get_kind_display(),
                "details": f"{m.quantity:+d}. {m.note}".strip(),
            }
        )
    for s in statuses.select_related("user", "order")[:limit]:
        rows.append(
            {
                "when": s.created_at,
                "user": s.user,
                "what": f"order: {s.order}",
                "action": f"{s.get_from_status_display()} -> {s.get_to_status_display()}",
                "details": s.note,
            }
        )
    rows.sort(key=lambda r: r["when"], reverse=True)
    return rows[:limit]


def activity_view(request):
    if not request.user.is_superuser:
        raise PermissionDenied
    user_id = request.GET.get("user") or None
    try:
        days = min(max(int(request.GET.get("days", 7)), 1), 90)
    except ValueError:
        days = 7
    staff = get_user_model().objects.filter(Q(is_staff=True) | Q(is_superuser=True))
    context = {
        **admin.site.each_context(request),
        "title": "Staff activity",
        "rows": _activity(user_id, days),
        "staff": staff.order_by("username"),
        "selected_user": int(user_id) if user_id and user_id.isdigit() else None,
        "days": days,
    }
    return TemplateResponse(request, "admin/staff_activity.html", context)


urlpatterns = [
    path("dashboard/", admin.site.admin_view(dashboard_view), name="admin_dashboard"),
    path("staff-activity/", admin.site.admin_view(activity_view), name="admin_staff_activity"),
]
