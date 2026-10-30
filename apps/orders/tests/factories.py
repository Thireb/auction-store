from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory

from apps.cart.cart import Cart
from apps.inventory import services as stock
from apps.orders.services import place_order
from apps.shipping.models import City


def make_order(variants_with_qty, phone="+923001234567", city=None, **customer):
    """Place a real order through the checkout service, so stock is reserved."""
    request = RequestFactory().get("/")
    request.session = SessionStore()
    cart = Cart(request)
    for variant, quantity in variants_with_qty:
        variant.refresh_from_db()
        if variant.stock_available < quantity:
            stock.receive(variant, quantity)
            variant.refresh_from_db()
        cart.add(variant, quantity)
    city = city or City.objects.get_or_create(name="Lahore")[0]
    data = {"full_name": "Ali Khan", "phone": phone, "city": city, "address": "House 1"}
    data.update(customer)
    return place_order(cart, data)
