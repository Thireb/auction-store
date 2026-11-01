from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.catalog import pricing
from apps.catalog.models import Variant
from apps.catalog.views import product_queryset
from apps.inventory import lots
from apps.shipping.models import City, ShippingSettings
from apps.shipping.services import quote as quote_fees

from .cart import Cart


def _quantity(request, default=1):
    try:
        return int(request.POST.get("quantity", default))
    except (TypeError, ValueError):
        return 0


def _cart_body(request, cart):
    if request.POST.get("drawer"):
        return drawer(request)
    context = {"cart": cart, "free": _free_delivery(cart) if cart.lines else None}
    return render(request, "cart/partials/cart_body.html", context)


def _free_delivery(cart):
    """(amount still needed, percent reached) for free delivery, or None if there is none."""
    limit = ShippingSettings.load().free_delivery_above
    if not limit:
        return None
    gap = max(limit - cart.subtotal, 0)
    return {"gap": gap, "ratio": min(cart.subtotal / limit, 1), "limit": limit}


def _suggestions(cart, limit=2):
    """Other pieces from the lot of the newest cart line, else the newest pieces."""
    in_cart = [line.product.pk for line in cart.lines]
    products = product_queryset().exclude(pk__in=in_cart)
    lot = lots.lot_for_product(cart.lines[-1].product) if cart.lines else None
    if lot:
        products = lots.lot_products(products, lot)
    return products[:limit]


def cart_detail(request):
    cart = Cart(request)
    context = {"cart": cart, "free": _free_delivery(cart) if cart.lines else None}
    return render(request, "cart/cart.html", context)


def drawer(request):
    """HTMX: the cart drawer content."""
    cart = Cart(request)
    context = {
        "cart": cart,
        "free": _free_delivery(cart) if cart.lines else None,
        "suggestions": _suggestions(cart) if cart.lines else [],
    }
    return render(request, "cart/partials/drawer.html", context)


def quote(request):
    """HTMX: the delivery fee and days for one city, for the product page."""
    city = City.objects.filter(
        pk=request.GET.get("city") or None, is_active=True, cod_allowed=True
    ).first()
    variant = (
        Variant.objects.filter(pk=request.GET.get("variant") or None, is_active=True)
        .select_related("product__category")
        .prefetch_related("price_tiers")
        .first()
    )
    if city is None or variant is None:
        return render(request, "cart/partials/quote.html", {})
    try:
        quantity = max(int(request.GET.get("quantity", 1)), 1)
    except ValueError:
        quantity = 1
    wholesale = pricing.buyer_is_wholesale(request.user)
    subtotal = pricing.line_total(variant, quantity, wholesale)
    fees = quote_fees(city, subtotal, has_bulky=variant.product.bulky)
    context = {"city": city, "fees": fees}
    return render(request, "cart/partials/quote.html", context)


@require_POST
def add(request):
    variant = get_object_or_404(
        Variant.objects.select_related("product"),
        pk=request.POST.get("variant"),
        is_active=True,
        product__is_active=True,
    )
    cart = Cart(request)
    quantity = _quantity(request)
    error = (
        "Choose a quantity of at least 1."
        if quantity < 1
        else pricing.quantity_error(variant, cart.quantity_of(variant) + quantity)
    )
    if not error:
        cart.add(variant, quantity)
    if request.htmx:
        response = render(
            request,
            "cart/partials/add_result.html",
            {"error": error, "cart": cart, "variant": variant},
        )
        if not error:
            response["HX-Trigger"] = "cart-open"
        return response
    if error:
        messages.error(request, error)
        return redirect(variant.product.get_absolute_url())
    messages.success(request, f"{variant} added to your cart.")
    return redirect("cart:detail")


@require_POST
def update(request, variant_id):
    cart = Cart(request)
    variant = get_object_or_404(Variant, pk=variant_id)
    cart.set(variant, max(_quantity(request, 0), 0))
    return _cart_body(request, cart) if request.htmx else redirect("cart:detail")


@require_POST
def remove(request, variant_id):
    cart = Cart(request)
    cart.remove(variant_id)
    return _cart_body(request, cart) if request.htmx else redirect("cart:detail")
