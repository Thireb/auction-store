"""Read the audit trail: django-simple-history rows, stock movements and order status changes."""

from datetime import timedelta

from django.utils import timezone
from simple_history.models import registered_models

from apps.inventory.models import StockMovement
from apps.orders.models import OrderStatusHistory

AUDITED_APPS = {"catalog", "inventory", "orders", "shipping", "accounts", "core"}
ACTIONS = {"+": "Created", "~": "Changed", "-": "Deleted"}


def _changes(record):
    if record.history_type != "~" or not record.prev_record:
        return ""
    delta = record.diff_against(record.prev_record)
    return "; ".join(f"{c.field}: {c.old} -> {c.new}" for c in delta.changes)


def _row(model, record):
    return {
        "when": record.history_date,
        "user": record.history_user,
        "what": f"{model._meta.verbose_name}: {record}",
        "action": ACTIONS[record.history_type],
        "details": _changes(record),
    }


def object_history(obj, limit=30):
    """Recent changes of one object, newest first."""
    history = getattr(obj, "history", None)
    if history is None:
        return []
    records = history.select_related("history_user").order_by("-history_date")[:limit]
    return [_row(type(obj), r) for r in records]


def activity(user_id=None, days=7, limit=300):
    """What staff did in the last `days` days, newest first."""
    since = timezone.now() - timedelta(days=days)
    rows = []
    for model in registered_models.values():
        if model._meta.app_label not in AUDITED_APPS:
            continue
        history = model.history.filter(history_date__gte=since, history_user__isnull=False)
        if user_id:
            history = history.filter(history_user_id=user_id)
        for record in history.select_related("history_user").order_by("-history_date")[:limit]:
            rows.append(_row(model, record))
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
