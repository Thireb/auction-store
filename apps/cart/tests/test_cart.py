import pytest
from django.urls import reverse

from apps.catalog.models import PriceTier
from apps.catalog.tests.factories import VariantFactory
from apps.inventory import services

pytestmark = pytest.mark.django_db


@pytest.fixture
def cable():
    variant = VariantFactory(price=650)
    services.receive(variant, 100)
    PriceTier.objects.create(variant=variant, min_quantity=10, unit_price=550)
    return variant


def add(client, variant, quantity, htmx=False):
    headers = {"HTTP_HX_REQUEST": "true"} if htmx else {}
    return client.post(
        reverse("cart:add"), {"variant": variant.pk, "quantity": quantity}, **headers
    )


def test_add_to_cart_with_htmx_updates_count(client, cable):
    response = add(client, cable, 2, htmx=True)
    content = response.content.decode()
    assert "Added to your cart" in content
    assert 'id="cart-count" hx-swap-oob="true">2<' in content


def test_cart_uses_tier_price(client, cable):
    add(client, cable, 10)
    content = client.get(reverse("cart:detail")).content.decode()
    assert "Rs 550" in content
    assert "Rs 5,500" in content
    assert "You save Rs 1,000" in content


def test_add_more_than_stock_is_refused(client):
    variant = VariantFactory()
    services.receive(variant, 1)
    add(client, variant, 1)
    response = add(client, variant, 1, htmx=True)
    assert "Only 1 available" in response.content.decode()
    assert client.session["cart"] == {str(variant.pk): 1}


def test_moq_is_enforced(client, cable):
    cable.min_order_qty = 5
    cable.save()
    response = add(client, cable, 2, htmx=True)
    assert "minimum order" in response.content.decode()


def test_update_and_remove(client, cable):
    add(client, cable, 2)
    headers = {"HTTP_HX_REQUEST": "true"}
    client.post(reverse("cart:update", args=[cable.pk]), {"quantity": 4}, **headers)
    assert client.session["cart"] == {str(cable.pk): 4}
    client.post(reverse("cart:remove", args=[cable.pk]), **headers)
    assert client.session["cart"] == {}


def test_hidden_product_drops_out_of_cart(client, cable):
    add(client, cable, 1)
    cable.product.is_active = False
    cable.product.save()
    content = client.get(reverse("cart:detail")).content.decode()
    assert "Your cart is empty" in content


def test_cart_line_error_blocks_checkout_button(client):
    variant = VariantFactory()
    services.receive(variant, 3)
    add(client, variant, 3)
    services.reserve(variant, 2)
    content = client.get(reverse("cart:detail")).content.decode()
    assert "Only 1 available" in content
    assert reverse("orders:checkout") not in content
