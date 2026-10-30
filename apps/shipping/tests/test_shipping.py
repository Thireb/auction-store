import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.shipping.models import City, ShippingSettings
from apps.shipping.services import quote

pytestmark = pytest.mark.django_db


@pytest.fixture
def store_settings():
    s = ShippingSettings.load()
    s.default_delivery_fee, s.default_cod_fee, s.bulky_item_fee = 250, 50, 2000
    s.save()
    return s


def test_settings_is_a_single_row():
    ShippingSettings.load()
    ShippingSettings(default_delivery_fee=300).save()
    assert ShippingSettings.objects.count() == 1
    assert ShippingSettings.load().default_delivery_fee == 300


def test_city_uses_defaults_or_own_fees(store_settings):
    lahore = City.objects.create(name="Lahore")
    skardu = City.objects.create(name="Skardu", delivery_fee=600, cod_fee=0)
    assert (quote(lahore, 1000).delivery_fee, quote(lahore, 1000).cod_fee) == (250, 50)
    assert (quote(skardu, 1000).delivery_fee, quote(skardu, 1000).cod_fee) == (600, 0)
    assert quote(lahore, 1000).total == 300


def test_free_delivery_and_bulky_fee(store_settings):
    store_settings.free_delivery_above = 5000
    store_settings.save()
    city = City.objects.create(name="Karachi")
    assert quote(city, 4999).delivery_fee == 250
    assert quote(city, 5000).delivery_fee == 0
    assert quote(city, 5000, has_bulky=True).delivery_fee == 2000


def test_settings_admin_opens_the_single_row(client):
    owner = get_user_model().objects.create_superuser("o", "o@example.com", "x")
    client.force_login(owner)
    response = client.get(reverse("admin:shipping_shippingsettings_changelist"))
    assert response.status_code == 302
    assert client.get(response.url).status_code == 200


def test_load_cities_is_idempotent():
    from django.core.management import call_command

    call_command("load_cities")
    count = City.objects.count()
    call_command("load_cities")
    assert count > 50
    assert City.objects.count() == count
    assert City.objects.first().name == "Karachi"
