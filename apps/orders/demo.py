"""Demo orders in every status, spread over the last weeks. Used by `manage.py seed_demo`.

Orders go through the real checkout and workflow code, so stock, history and money match.
"""

import random
from datetime import timedelta
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.base import SessionBase
from django.utils import timezone

from apps.accounts.demo import CUSTOMERS, WHOLESALE
from apps.cart.cart import Cart
from apps.catalog import pricing
from apps.catalog.models import Variant
from apps.inventory.demo import BULK_CATEGORIES
from apps.shipping.models import City

from . import workflow
from .models import Order
from .services import CheckoutError, place_order

DEMO_NOTE = "Demo order"
COURIERS = ["TCS", "Leopards", "M&P", "Trax", "PostEx"]
# Final status and how many orders end there.
PLAN = [
    (Order.COMPLETED, 16),
    (Order.DELIVERED, 5),
    (Order.SHIPPED, 6),
    (Order.PACKED, 4),
    (Order.CONFIRMED, 5),
    (Order.PENDING, 8),
    (Order.CANCELLED, 4),
    (Order.RETURNED, 2),
]
PATHS = {
    Order.PENDING: [],
    Order.CONFIRMED: [Order.CONFIRMED],
    Order.PACKED: [Order.CONFIRMED, Order.PACKED],
    Order.SHIPPED: [Order.CONFIRMED, Order.PACKED, Order.SHIPPED],
    Order.DELIVERED: [Order.CONFIRMED, Order.SHIPPED, Order.DELIVERED],
    Order.COMPLETED: [
        Order.CONFIRMED,
        Order.PACKED,
        Order.SHIPPED,
        Order.DELIVERED,
        Order.COMPLETED,
    ],
    Order.CANCELLED: [Order.CANCELLED],
    Order.RETURNED: [Order.CONFIRMED, Order.SHIPPED, Order.RETURNED],
}
ADDRESSES = [
    "House 12, Street 4, Block B",
    "Flat 7, Al-Rehman Heights, Main Boulevard",
    "Shop 3, Main Market",
    "House 45-C, Phase 2",
    "Plot 88, Sector F",
]


def _cart(user):
    request = SimpleNamespace(session=SessionBase(), user=user)
    return Cart(request)


def _fill(cart, rng, singles, bulk, wholesale):
    if wholesale:
        picks = rng.sample(bulk, k=min(len(bulk), rng.randint(1, 3)))
        sizes = [50, 100, 120, 150]
    else:
        picks = rng.sample(singles, k=rng.randint(1, 3))
        if rng.random() < 0.25:
            picks.append(rng.choice(bulk))
        sizes = [1, 1, 1, 2, 10, 15]
    for variant in picks:
        variant.refresh_from_db()
        quantity = pricing.nearest_valid_quantity(variant, rng.choice(sizes))
        if not pricing.quantity_error(variant, quantity):
            cart.add(variant, quantity)


def _move(order, final, staff, rng):
    if order.advance_status == Order.ADVANCE_PENDING and final not in (
        Order.PENDING,
        Order.CANCELLED,
    ):
        workflow.transition(order, Order.AWAITING_ADVANCE, user=staff)
        order = workflow.mark_advance_received(
            order, user=staff, note="Bank transfer screenshot checked."
        )
    for target in PATHS[final]:
        extra = {}
        if target == Order.SHIPPED:
            extra = {
                "courier": rng.choice(COURIERS),
                "tracking_number": f"{rng.randint(10**9, 10**10 - 1)}",
            }
        note = {
            Order.CONFIRMED: "Customer confirmed by phone.",
            Order.CANCELLED: "Customer did not answer 3 calls.",
            Order.RETURNED: "Customer refused the parcel.",
            Order.COMPLETED: "Cash received from courier.",
        }.get(target, "")
        order = workflow.transition(order, target, user=staff, note=note, **extra)
    return order


def seed_orders(stdout=None):
    if Order.objects.filter(staff_notes=DEMO_NOTE).exists():
        return
    User = get_user_model()
    staff = User.objects.filter(username="demo-orders").first()
    if staff is None:
        return
    rng = random.Random(11)
    variants = list(
        Variant.objects.filter(is_active=True, stock_on_hand__gt=0)
        .select_related("product__category__parent")
        .order_by("pk")
    )

    def is_bulk(v):
        c = v.product.category
        return bool({c.name, c.parent.name if c.parent else ""} & BULK_CATEGORIES)

    bulk = [v for v in variants if is_bulk(v)]
    singles = [v for v in variants if not is_bulk(v) and v.product.category.parent_id]
    cities = {c.name: c for c in City.objects.filter(is_active=True, cod_allowed=True)}
    buyers = [
        (User.objects.get(username=p), first, last, city) for p, first, last, city in CUSTOMERS
    ]
    traders = [
        (User.objects.get(username=p), first, last, city)
        for p, first, last, city, _b, status in WHOLESALE
        if status == "approved"
    ]
    guests = [
        (None, "Waqas", "Ali", "Lahore", "+923003330001"),
        (None, "Saima", "Bano", "Karachi", "+923003330002"),
        (None, "Adeel", "Zafar", "Islamabad", "+923003330003"),
        (None, "Komal", "Rashid", "Faisalabad", "+923003330004"),
    ]

    finals = [status for status, count in PLAN for _ in range(count)]
    rng.shuffle(finals)
    now = timezone.now()
    made = 0
    for n, final in enumerate(finals):
        wholesale = n % 7 == 3
        if wholesale:
            user, first, last, city = traders[n % len(traders)]
            phone = user.username
        elif n % 5 == 4:
            user, first, last, city, phone = guests[n % len(guests)]
        else:
            user, first, last, city = buyers[n % len(buyers)]
            phone = user.username
        if Order.objects.filter(phone=phone, status__in=Order.OPEN_STATUSES).count() >= 2:
            final = Order.COMPLETED
        cart = _cart(user)
        _fill(cart, rng, singles, bulk, wholesale)
        if not cart.lines:
            continue
        customer = {
            "full_name": f"{first} {last}",
            "phone": phone,
            "email": user.email if user else "",
            "city": cities.get(city) or next(iter(cities.values())),
            "address": rng.choice(ADDRESSES),
            "landmark": "Near the main mosque" if n % 3 == 0 else "",
            "notes": "Please call before delivery." if n % 4 == 0 else "",
        }
        try:
            order = place_order(cart, customer, user=user)
        except CheckoutError:
            continue
        order = _move(order, final, staff, rng)
        # Spread the orders over the last 6 weeks; open orders are the newest.
        days = rng.randint(0, 3) if final in Order.OPEN_STATUSES else rng.randint(4, 42)
        created = now - timedelta(days=days, hours=rng.randint(0, 20))
        Order.objects.filter(pk=order.pk).update(staff_notes=DEMO_NOTE, created_at=created)
        made += 1
    if stdout:
        stdout.write(f"Orders: {made} demo orders in every status.")
