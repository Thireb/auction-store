import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.catalog.tests.factories import VariantFactory
from apps.orders.models import Order

from .factories import make_order

pytestmark = pytest.mark.django_db


@pytest.fixture
def owner_client(client):
    client.force_login(get_user_model().objects.create_superuser("owner", "o@x.com", "x"))
    return client


@pytest.fixture
def order():
    return make_order([(VariantFactory(price=2500), 1)])


def test_change_page_shows_buttons_and_contact_links(owner_client, order):
    content = owner_client.get(
        reverse("admin:orders_order_change", args=[order.pk])
    ).content.decode()
    assert "Next step" in content
    assert reverse("admin:orders_order_transition", args=[order.pk, Order.CONFIRMED]) in content
    assert "https://wa.me/923001234567?text=" in content
    assert 'href="tel:+923001234567"' in content


def test_transition_view(owner_client, order):
    url = reverse("admin:orders_order_transition", args=[order.pk, Order.CONFIRMED])
    assert owner_client.get(url).status_code == 200
    response = owner_client.post(url, {"note": "Called, confirmed"})
    assert response.status_code == 302
    order.refresh_from_db()
    assert order.status == Order.CONFIRMED
    assert order.status_history.first().note == "Called, confirmed"


def test_shipping_needs_courier(owner_client, order):
    owner_client.post(reverse("admin:orders_order_transition", args=[order.pk, Order.CONFIRMED]))
    url = reverse("admin:orders_order_transition", args=[order.pk, Order.SHIPPED])
    response = owner_client.post(url, {})
    assert "Enter the courier" in response.content.decode()
    owner_client.post(url, {"courier": "PostEx", "tracking_number": "PX1"})
    order.refresh_from_db()
    assert order.status == Order.SHIPPED


def test_bulk_confirm_action(owner_client, order):
    response = owner_client.post(
        reverse("admin:orders_order_changelist"),
        {"action": "confirm_orders", "_selected_action": [order.pk]},
    )
    assert response.status_code == 302
    order.refresh_from_db()
    assert order.status == Order.CONFIRMED


def test_print_view(owner_client, order):
    content = owner_client.get(
        reverse("admin:orders_order_print", args=[order.pk])
    ).content.decode()
    assert order.number in content
    assert "COD: Rs" in content


def test_advance_button_is_not_a_nested_form(owner_client, order):
    # A <form> inside the admin change form is dropped by the browser, and the button then
    # submitted the change form instead.
    Order.objects.filter(pk=order.pk).update(
        advance_amount=500, advance_status=Order.ADVANCE_PENDING
    )
    url = reverse("admin:orders_order_advance", args=[order.pk])
    content = owner_client.get(
        reverse("admin:orders_order_change", args=[order.pk])
    ).content.decode()
    assert f'formaction="{url}"' in content
    assert f'action="{url}"' not in content.replace(f'formaction="{url}"', "")
    assert owner_client.post(url).status_code == 302
    order.refresh_from_db()
    assert order.advance_status == Order.ADVANCE_RECEIVED
