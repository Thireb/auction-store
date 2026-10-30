import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse

from apps.catalog.tests.factories import VariantFactory
from apps.inventory.models import Lot, StockMovement

pytestmark = pytest.mark.django_db


def staff_client(client, *codenames):
    user = get_user_model().objects.create_user("staff", password="x", is_staff=True)
    user.user_permissions.add(*Permission.objects.filter(codename__in=codenames))
    client.force_login(user)
    return client


def test_receive_stock_through_admin(client):
    c = staff_client(client, "add_stockmovement", "view_stockmovement")
    variant = VariantFactory()
    lot = Lot.objects.create(reference="L1")
    response = c.post(
        reverse("admin:inventory_stockmovement_add"),
        {"variant": variant.pk, "kind": "received", "quantity": 4, "lot": lot.pk, "note": ""},
    )
    assert response.status_code == 302
    variant.refresh_from_db()
    assert variant.stock_on_hand == 4
    assert StockMovement.objects.get().user.username == "staff"


def test_adjust_without_permission_shows_error(client):
    c = staff_client(client, "add_stockmovement", "view_stockmovement")
    variant = VariantFactory()
    response = c.post(
        reverse("admin:inventory_stockmovement_add"),
        {"variant": variant.pk, "kind": "adjustment", "quantity": 4, "note": "x"},
    )
    assert response.status_code == 200
    assert "permission to adjust" in response.content.decode()
    variant.refresh_from_db()
    assert variant.stock_on_hand == 0


def test_cost_hidden_without_permission(client):
    c = staff_client(client, "view_lot", "change_lot")
    lot = Lot.objects.create(reference="L2", total_cost=50000)
    content = c.get(reverse("admin:inventory_lot_change", args=[lot.pk])).content.decode()
    assert "total_cost" not in content


def test_cost_visible_with_permission(client):
    c = staff_client(client, "view_lot", "change_lot", "view_cost_and_profit")
    lot = Lot.objects.create(reference="L3", total_cost=50000)
    content = c.get(reverse("admin:inventory_lot_change", args=[lot.pk])).content.decode()
    assert "total_cost" in content


def test_movements_cannot_be_edited_or_deleted(client):
    c = staff_client(client, "view_stockmovement", "change_stockmovement", "delete_stockmovement")
    variant = VariantFactory()
    from apps.inventory import services

    services.receive(variant, 1)
    movement = StockMovement.objects.get()
    url = reverse("admin:inventory_stockmovement_delete", args=[movement.pk])
    assert c.post(url, {"post": "yes"}).status_code == 403


def test_low_stock_filter(client):
    from apps.inventory import services

    c = staff_client(client, "view_variant")
    low = VariantFactory(sku="LOW-1")
    services.receive(low, 1)
    ok = VariantFactory(sku="OK-1")
    services.receive(ok, 50)
    content = c.get(reverse("admin:catalog_variant_changelist") + "?stock=low").content.decode()
    assert "LOW-1" in content
    assert "OK-1" not in content
