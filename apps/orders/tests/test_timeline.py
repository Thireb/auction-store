import pytest
from django.urls import reverse
from django.utils import timezone

from apps.catalog.tests.factories import ProductFactory, VariantFactory
from apps.inventory import services
from apps.inventory.models import Lot
from apps.orders import timeline
from apps.orders.models import Order
from apps.shipping.models import City

from .factories import make_order

pytestmark = pytest.mark.django_db


def states(order):
    return [(step["title"], step["state"]) for step in timeline.steps(order)]


def test_new_order_waits_for_the_call():
    order = make_order([(VariantFactory(), 1)])
    # The time is in Asia/Karachi, not UTC.
    local = timezone.localtime(order.created_at)
    assert timeline.steps(order)[0]["detail"] == local.strftime("%-d %B, %-I:%M ") + local.strftime(
        "%p"
    )
    assert states(order)[:3] == [
        ("Order placed", "done"),
        ("We call you to confirm", "now"),
        ("Packed", "todo"),
    ]


def test_cancelled_order_stops_the_timeline():
    order = make_order([(VariantFactory(), 1)])
    order.status = Order.CANCELLED  # Display only: the workflow is tested elsewhere.
    assert states(order) == [("Order placed", "done"), ("Cancelled", "stopped")]


def test_thanks_page_shows_progress_and_more_from_the_lot(client):
    lot = Lot.objects.create(reference="DXB-55", is_public=True, public_title="Hotel refit")
    sofa = VariantFactory(product=ProductFactory(title="Grey sofa"))
    desk = VariantFactory(product=ProductFactory(title="Oak desk"))
    for variant in (sofa, desk):
        services.receive(variant, 1, lot=lot)
    client.post(reverse("cart:add"), {"variant": sofa.pk, "quantity": 1})
    city = City.objects.create(name="Lahore")
    data = {"full_name": "Ali Khan", "phone": "03001234567", "city": city.pk, "address": "House 1"}
    response = client.post(reverse("orders:checkout"), data)
    content = client.get(response.url).content.decode()
    assert "We call you to confirm" in content
    assert "While you wait" in content
    assert "Oak desk" in content
    assert reverse("lots:dig", args=[lot.slug]) in content
