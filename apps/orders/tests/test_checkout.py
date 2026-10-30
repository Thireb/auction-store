import threading

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.urls import reverse

from apps.catalog.models import ADVANCE_PERCENT
from apps.catalog.tests.factories import CategoryFactory, ProductFactory, VariantFactory
from apps.inventory import services as stock
from apps.orders import services
from apps.orders.models import BlockedPhone, Order
from apps.shipping.models import City, ShippingSettings

pytestmark = pytest.mark.django_db


@pytest.fixture
def city():
    s = ShippingSettings.load()
    s.default_delivery_fee, s.default_cod_fee = 250, 0
    s.save()
    return City.objects.create(name="Lahore")


@pytest.fixture
def watch():
    variant = VariantFactory(price=5000, product=ProductFactory(title="Analog watch"))
    stock.receive(variant, 3)
    return variant


def fill_cart(client, variant, quantity=1):
    client.post(reverse("cart:add"), {"variant": variant.pk, "quantity": quantity})


def checkout_data(city, **extra):
    data = {
        "full_name": "Ali Khan",
        "phone": "0300 1234567",
        "city": city.pk,
        "address": "House 1, Street 2, Gulberg",
    }
    data.update(extra)
    return data


def test_checkout_creates_order_and_reserves_stock(client, city, watch):
    fill_cart(client, watch, 2)
    response = client.post(reverse("orders:checkout"), checkout_data(city))
    order = Order.objects.get()
    assert response.status_code == 302
    assert response.url == order.get_thanks_url()
    assert order.number.startswith("AS-")
    assert (order.subtotal, order.delivery_fee, order.total) == (10000, 250, 10250)
    assert order.phone == "+923001234567"
    assert order.status == Order.PENDING
    item = order.items.get()
    assert (item.product_title, item.quantity, item.unit_price) == ("Analog watch", 2, 5000)
    watch.refresh_from_db()
    assert watch.stock_reserved == 2
    assert client.session["cart"] == {}
    content = client.get(response.url).content.decode()
    assert order.number in content
    assert "0300 1234567" in content


def test_thanks_page_is_private(client, city, watch):
    fill_cart(client, watch)
    client.post(reverse("orders:checkout"), checkout_data(city))
    order = Order.objects.get()
    client.cookies.clear()
    assert client.get(order.get_thanks_url()).status_code == 404


def test_fee_summary_updates_with_htmx(client, city, watch):
    fill_cart(client, watch)
    response = client.get(reverse("orders:checkout"), {"city": city.pk}, HTTP_HX_REQUEST="true")
    content = response.content.decode()
    assert "Rs 250" in content and "Rs 5,250" in content


def test_invalid_phone_shows_error(client, city, watch):
    fill_cart(client, watch)
    response = client.post(reverse("orders:checkout"), checkout_data(city, phone="12345"))
    assert response.status_code == 200
    assert "Pakistani mobile number" in response.content.decode()
    assert not Order.objects.exists()


def test_empty_cart_redirects(client):
    assert client.get(reverse("orders:checkout")).url == reverse("cart:detail")


def test_create_account_at_checkout(client, city, watch):
    fill_cart(client, watch)
    data = checkout_data(
        city, create_account="on", password="a-Strong-pass-42", email="ali@example.com"
    )
    client.post(reverse("orders:checkout"), data)
    user = get_user_model().objects.get(username="+923001234567")
    assert user.check_password("a-Strong-pass-42")
    assert Order.objects.get().user == user
    assert int(client.session["_auth_user_id"]) == user.pk


def test_create_account_needs_password(client, city, watch):
    fill_cart(client, watch)
    response = client.post(reverse("orders:checkout"), checkout_data(city, create_account="on"))
    assert "Choose a password" in response.content.decode()


def test_stock_taken_by_someone_else_stops_checkout(client, city, watch):
    fill_cart(client, watch, 3)
    stock.reserve(watch, 2)
    response = client.post(reverse("orders:checkout"), checkout_data(city))
    assert response.status_code == 302
    assert response.url == reverse("cart:detail")
    assert not Order.objects.exists()


def test_advance_for_percent_category(client, city):
    furniture = CategoryFactory(name="Furniture", advance_type=ADVANCE_PERCENT, advance_value=20)
    sofa = VariantFactory(price=100000, product=ProductFactory(category=furniture))
    stock.receive(sofa, 1)
    fill_cart(client, sofa)
    response = client.post(reverse("orders:checkout"), checkout_data(city))
    order = Order.objects.get()
    assert order.advance_amount == 20000
    assert order.advance_status == Order.ADVANCE_PENDING
    assert order.balance_after_advance == 80250
    assert "Rs 20,000" in client.get(response.url).content.decode()


def test_store_wide_advance_rule(city):
    s = ShippingSettings.load()
    s.advance_above_total, s.advance_percent_above_total = 50000, 10
    lines = []
    assert services.order_advance(lines, 49999, s) == 0
    assert services.order_advance(lines, 60000, s) == 6000


def test_upload_advance_proof(client, city, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    category = CategoryFactory(advance_type=ADVANCE_PERCENT, advance_value=10)
    variant = VariantFactory(price=10000, product=ProductFactory(category=category))
    stock.receive(variant, 1)
    fill_cart(client, variant)
    client.post(reverse("orders:checkout"), checkout_data(city))
    order = Order.objects.get()
    from io import BytesIO

    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (10, 10)).save(buffer, format="PNG")
    upload = SimpleUploadedFile("proof.png", buffer.getvalue(), content_type="image/png")
    response = client.post(
        reverse("orders:advance_proof", args=[order.number]), {"advance_proof": upload}
    )
    assert response.status_code == 302
    order.refresh_from_db()
    assert order.advance_proof


def test_blocked_phone_cannot_order(client, city, watch):
    BlockedPhone.objects.create(phone="+923001234567", reason="Refused 3 parcels")
    fill_cart(client, watch)
    response = client.post(reverse("orders:checkout"), checkout_data(city))
    assert "cannot take orders from this number" in response.content.decode()
    assert not Order.objects.exists()


def test_open_order_limit_per_phone(client, city, watch, settings):
    settings.MAX_OPEN_ORDERS_PER_PHONE = 1
    fill_cart(client, watch)
    client.post(reverse("orders:checkout"), checkout_data(city))
    fill_cart(client, watch)
    response = client.post(reverse("orders:checkout"), checkout_data(city))
    assert "already has orders in progress" in response.content.decode()
    assert Order.objects.count() == 1


def test_orders_per_ip_limit(client, city, watch, settings):
    settings.MAX_ORDERS_PER_IP_PER_HOUR = 1
    fill_cart(client, watch)
    client.post(reverse("orders:checkout"), checkout_data(city))
    fill_cart(client, watch)
    response = client.post(reverse("orders:checkout"), checkout_data(city, phone="03111234567"))
    assert "Too many orders" in response.content.decode()


def test_city_without_cod_is_not_offered(client, city, watch):
    City.objects.create(name="Far town", cod_allowed=False)
    fill_cart(client, watch)
    assert "Far town" not in client.get(reverse("orders:checkout")).content.decode()


@pytest.mark.django_db(transaction=True)
def test_two_buyers_cannot_buy_the_last_piece():
    variant = VariantFactory(price=1000)
    stock.receive(variant, 1)
    results = []

    def buy():
        try:
            stock.reserve(variant, 1)
            results.append("ok")
        except stock.InsufficientStock:
            results.append("sold out")
        finally:
            connection.close()

    threads = [threading.Thread(target=buy) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == ["ok", "sold out"]
    variant.refresh_from_db()
    assert variant.stock_reserved == 1
