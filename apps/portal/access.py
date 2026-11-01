"""Who can open which part of the staff portal.

The portal uses the same Django permissions and groups as before (see apps/core/roles.py).
The owner is a superuser and has every permission. Staff accounts need `is_staff`.
"""

from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.urls import reverse


def is_portal_user(user):
    return user.is_authenticated and user.is_active and (user.is_staff or user.is_superuser)


def portal_view(perm=None, owner=False):
    """Decorate a portal view. `perm` is one permission or a list (all needed)."""
    perms = [perm] if isinstance(perm, str) else list(perm or [])

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not is_portal_user(request.user):
                return redirect_to_login(request.get_full_path(), reverse("portal:login"))
            if owner and not request.user.is_superuser:
                raise PermissionDenied
            if perms and not request.user.has_perms(perms):
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


# The side menu: (section, [(label, url name, permission or "owner")]).
MENU = [
    ("", [("Dashboard", "portal:dashboard", None)]),
    (
        "Orders",
        [
            ("Orders", "portal:order_list", "orders.view_order"),
            ("Wholesale buyers", "portal:wholesale_list", "accounts.view_wholesaleprofile"),
            ("Blocked phones", "portal:blockedphone_list", "orders.view_blockedphone"),
        ],
    ),
    (
        "Catalog",
        [
            ("Products", "portal:product_list", "catalog.view_product"),
            ("Categories", "portal:category_list", "catalog.view_category"),
            ("Attributes", "portal:attribute_list", "catalog.view_attribute"),
            ("Brands", "portal:brand_list", "catalog.view_brand"),
        ],
    ),
    (
        "Stock",
        [
            ("Stock levels", "portal:stock_list", "catalog.view_variant"),
            ("Near empty", "portal:stock_near_empty", "catalog.view_variant"),
            ("Out of stock", "portal:stock_out", "catalog.view_variant"),
            ("Stock movements", "portal:movement_list", "inventory.view_stockmovement"),
            ("Lots", "portal:lot_list", "inventory.view_lot"),
            ("Photo trays", "portal:tray_list", "inventory.view_lotphoto"),
            ("Import CSV", "portal:import_csv", "inventory.add_stockmovement"),
        ],
    ),
    (
        "Store settings",
        [
            ("Fees, payment and stock", "portal:settings", "shipping.change_shippingsettings"),
            ("Cities", "portal:city_list", "shipping.view_city"),
            ("Pages", "portal:page_list", "core.view_page"),
        ],
    ),
    (
        "Owner",
        [
            ("Staff accounts", "portal:staff_list", "owner"),
            ("Staff activity", "portal:activity", "owner"),
        ],
    ),
]


def menu_for(user, path=""):
    sections = []
    for title, items in MENU:
        allowed = [
            (label, reverse(name))
            for label, name, perm in items
            if perm is None
            or (perm == "owner" and user.is_superuser)
            or (perm != "owner" and user.has_perm(perm))
        ]
        if allowed:
            sections.append((title, allowed))
    # Highlight the menu item with the longest URL that starts the current path.
    urls = [url for _, items in sections for _, url in items]
    home = reverse("portal:dashboard")
    matches = [u for u in urls if path == u or (u != home and path.startswith(u))]
    current = max(matches, key=len) if matches else None
    return [
        (title, [(label, url, url == current) for label, url in items]) for title, items in sections
    ]
