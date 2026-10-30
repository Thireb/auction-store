from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.catalog import pricing
from apps.catalog.models import Variant

from .cart import Cart


def _quantity(request, default=1):
    try:
        return int(request.POST.get("quantity", default))
    except (TypeError, ValueError):
        return 0


def _cart_body(request, cart):
    return render(request, "cart/partials/cart_body.html", {"cart": cart})


def cart_detail(request):
    return render(request, "cart/cart.html", {"cart": Cart(request)})


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
        return render(
            request,
            "cart/partials/add_result.html",
            {"error": error, "cart": cart, "variant": variant},
        )
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
