import datetime

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.catalog.models import Product, SavedProduct
from apps.catalog.saved import SESSION_KEY
from apps.inventory import services
from apps.shipping.models import City, ShippingSettings

from .factories import ProductFactory, VariantFactory

pytestmark = pytest.mark.django_db


def in_stock(title="Oak table", price=1000, quantity=1):
    variant = VariantFactory(product=ProductFactory(title=title), price=price)
    services.receive(variant, quantity)
    return variant


def test_guest_saves_and_unsaves_with_htmx(client):
    product = in_stock().product
    url = reverse("catalog:saved_toggle", args=[product.pk])
    content = client.post(url, HTTP_HX_REQUEST="true").content.decode()
    assert 'aria-pressed="true"' in content
    assert "just-saved" in content
    assert 'id="saved-count" class="badge badge-tag" hx-swap-oob="true">1<' in content
    assert client.session[SESSION_KEY] == [product.pk]

    content = client.post(url, HTTP_HX_REQUEST="true").content.decode()
    assert 'aria-pressed="false"' in content
    assert client.session[SESSION_KEY] == []


def test_save_without_javascript_goes_back(client):
    product = in_stock().product
    url = reverse("catalog:saved_toggle", args=[product.pk])
    response = client.post(url, {"next": "/products/"})
    assert response.url == "/products/"
    response = client.post(url, {"next": "https://evil.example/"})
    assert response.url == product.get_absolute_url()


def test_saved_page_splits_available_and_gone(client):
    here = in_stock("Brass lamp").product
    gone_variant = in_stock("Glass table")
    for product in (here, gone_variant.product):
        client.post(reverse("catalog:saved_toggle", args=[product.pk]))
    services.reserve(gone_variant, 1)
    content = client.get(reverse("catalog:saved")).content.decode()
    available, gone = content.split("Gone since you saved them")
    assert "Brass lamp" in available
    assert "Glass table" in gone and "SOLD" in gone


def test_login_moves_guest_saves_into_the_account(client):
    product = in_stock().product
    client.post(reverse("catalog:saved_toggle", args=[product.pk]))
    user = get_user_model().objects.create_user("+923001112233", password="pass-1234")
    client.post(reverse("accounts:login"), {"username": "0300 1112233", "password": "pass-1234"})
    assert SavedProduct.objects.filter(user=user, product=product).exists()
    # Saved for the account now: unsave removes the row.
    client.post(reverse("catalog:saved_toggle", args=[product.pk]))
    assert not SavedProduct.objects.filter(user=user).exists()


def test_product_page_remembers_recently_viewed(client):
    first = in_stock("Teak bench").product
    second = in_stock("Wall clock").product
    client.get(first.get_absolute_url())
    content = client.get(second.get_absolute_url()).content.decode()
    assert "You looked at" in content
    assert "Teak bench" in content.split("You looked at")[1]


def test_product_page_shows_condition_notes_and_scale(client):
    variant = in_stock()
    Product.objects.filter(pk=variant.product_id).update(
        condition="open_box", condition_notes="Box opened.\n\nOne scuff on a wheel."
    )
    content = client.get(variant.product.get_absolute_url()).content.decode()
    assert "Condition: open box" in content
    assert "<li>Box opened.</li>" in content and "<li>One scuff on a wheel.</li>" in content
    assert 'class="is-filled is-here">Open box' in content


def test_just_sold_shows_for_a_few_days(client, settings):
    settings.SOLD_VISIBLE_DAYS = 3
    fresh, old = in_stock("Fresh mirror"), in_stock("Old mirror")
    services.reserve(fresh, 1)
    services.reserve(old, 1)
    Product.objects.filter(pk=old.product_id).update(
        sold_out_at=timezone.now() - datetime.timedelta(days=4)
    )
    content = client.get(reverse("core:home")).content.decode()
    assert "Just sold" in content
    assert "Fresh mirror" in content and "Old mirror" not in content


def test_add_to_cart_opens_the_drawer(client):
    variant = in_stock(quantity=3)
    ShippingSettings.objects.update_or_create(pk=1, defaults={"free_delivery_above": 5000})
    response = client.post(
        reverse("cart:add"), {"variant": variant.pk, "quantity": 2}, HTTP_HX_REQUEST="true"
    )
    assert response["HX-Trigger"] == "cart-open"
    content = client.get(reverse("cart:drawer"), HTTP_HX_REQUEST="true").content.decode()
    assert "Oak table" in content
    assert "Add Rs 3,000 more for free delivery." in content
    assert reverse("orders:checkout") in content


def test_failed_add_does_not_open_the_drawer(client):
    variant = in_stock(quantity=1)
    response = client.post(
        reverse("cart:add"), {"variant": variant.pk, "quantity": 5}, HTTP_HX_REQUEST="true"
    )
    assert "HX-Trigger" not in response


def test_delivery_quote_for_a_city(client):
    variant = in_stock(price=2000, quantity=5)
    city = City.objects.create(name="Multan", delivery_fee=550, estimated_days="3-5")
    content = client.get(
        reverse("cart:quote"), {"city": city.pk, "variant": variant.pk, "quantity": 2}
    ).content.decode()
    assert "Delivery to Multan: Rs 550." in content
    assert "Arrives in 3-5 days." in content
    content = client.get(reverse("cart:quote"), {"city": "", "variant": variant.pk}).content
    assert b"Choose your city" in content
