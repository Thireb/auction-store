from apps.inventory import levels

from .access import is_portal_user, menu_for

ALERT_LIMIT = 15


def portal(request):
    """The side menu and the near-empty stock alerts, only on portal pages."""
    match = getattr(request, "resolver_match", None)
    if not match or match.app_name != "portal" or not is_portal_user(request.user):
        return {}
    context = {"portal_menu": menu_for(request.user, request.path)}
    if request.user.has_perm("catalog.view_variant"):
        low = levels.near_empty().select_related("product").order_by("available", "pk")
        context["stock_alerts"] = list(low[:ALERT_LIMIT])
        context["stock_alert_count"] = low.count()
    return context
