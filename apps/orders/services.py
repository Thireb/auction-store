"""Order creation. Order status changes come in phase 5 (apps/orders/workflow.py)."""

from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.catalog import pricing
from apps.catalog.models import ADVANCE_FIXED, ADVANCE_PERCENT
from apps.inventory import services as stock
from apps.shipping.models import ShippingSettings
from apps.shipping.services import quote

from .models import BlockedPhone, Order, OrderItem


class CheckoutError(Exception):
    pass


def _percent(amount, percent):
    return (Decimal(amount) * Decimal(percent) / 100).quantize(Decimal("1"), ROUND_HALF_UP)


def line_advance(product, unit_price, quantity):
    kind, value = product.advance_rule()
    if kind == ADVANCE_FIXED:
        return min(Decimal(value), unit_price) * quantity
    if kind == ADVANCE_PERCENT:
        return _percent(unit_price * quantity, min(value, 100))
    return Decimal(0)


def order_advance(lines, total, shipping_settings):
    """The advance for an order: product and category rules, or the store-wide rule if larger."""
    from_items = sum(
        (line_advance(line.product, line.unit_price, line.quantity) for line in lines), Decimal(0)
    )
    store_rule = Decimal(0)
    s = shipping_settings
    if s.advance_above_total is not None and total >= s.advance_above_total:
        store_rule = _percent(total, min(s.advance_percent_above_total, 100))
    return min(max(from_items, store_rule), total)


def summarize(cart, city, shipping_settings=None):
    """Totals for the checkout page and for the order."""
    shipping_settings = shipping_settings or ShippingSettings.load()
    subtotal = cart.subtotal
    fees = quote(city, subtotal, cart.has_bulky, shipping_settings) if city else None
    total = subtotal + (fees.total if fees else 0)
    return {
        "subtotal": subtotal,
        "delivery_fee": fees.delivery_fee if fees else None,
        "cod_fee": fees.cod_fee if fees else None,
        "total": total,
        "advance": order_advance(cart.lines, total, shipping_settings) if fees else Decimal(0),
    }


def check_customer_limits(phone, ip_address):
    if BlockedPhone.objects.filter(phone=phone).exists():
        raise CheckoutError(
            "We cannot take orders from this number online. Please contact us by phone."
        )
    open_orders = Order.objects.filter(phone=phone, status__in=Order.OPEN_STATUSES).count()
    if open_orders >= settings.MAX_OPEN_ORDERS_PER_PHONE:
        raise CheckoutError(
            "This number already has orders in progress. We will call you about them first."
        )
    if ip_address:
        hour_ago = timezone.now() - timedelta(hours=1)
        recent = Order.objects.filter(ip_address=ip_address, created_at__gte=hour_ago).count()
        if recent >= settings.MAX_ORDERS_PER_IP_PER_HOUR:
            raise CheckoutError("Too many orders from your connection. Please try again later.")


@transaction.atomic
def place_order(cart, customer, *, user=None, ip_address=None):
    """Create an order from the cart and reserve its stock. All or nothing.

    `customer` has: full_name, phone (normalized), email, city, address, landmark, notes.
    """
    lines = cart.lines
    if not lines:
        raise CheckoutError("Your cart is empty.")
    city = customer["city"]
    if not (city.is_active and city.cod_allowed):
        raise CheckoutError(f"Cash on Delivery is not available in {city.name}.")
    check_customer_limits(customer["phone"], ip_address)

    # Check the rules again: stock or prices may have changed since the cart page.
    for line in lines:
        error = pricing.quantity_error(line.variant, line.quantity)
        if error:
            raise CheckoutError(f"{line.variant}: {error}")

    shipping_settings = ShippingSettings.load()
    totals = summarize(cart, city, shipping_settings)
    order = Order.objects.create(
        user=user if user and user.is_authenticated else None,
        full_name=customer["full_name"],
        phone=customer["phone"],
        email=customer.get("email", ""),
        city=city,
        city_name=city.name,
        address=customer["address"],
        landmark=customer.get("landmark", ""),
        customer_notes=customer.get("notes", ""),
        subtotal=totals["subtotal"],
        delivery_fee=totals["delivery_fee"],
        cod_fee=totals["cod_fee"],
        total=totals["total"],
        advance_amount=totals["advance"],
        advance_status=Order.ADVANCE_PENDING if totals["advance"] else Order.ADVANCE_NOT_REQUIRED,
        ip_address=ip_address,
    )
    for line in lines:
        try:
            stock.reserve(line.variant, line.quantity, reference=order.number)
        except stock.InsufficientStock as exc:
            raise CheckoutError(str(exc)) from exc
        OrderItem.objects.create(
            order=order,
            variant=line.variant,
            product_title=line.product.title,
            variant_name=line.variant.name,
            sku=line.variant.sku,
            unit_price=line.unit_price,
            regular_price=line.variant.price,
            quantity=line.quantity,
            line_total=line.line_total,
            advance_amount=line_advance(line.product, line.unit_price, line.quantity),
        )
    cart.clear()
    return order
