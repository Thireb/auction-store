import io

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

from apps.catalog.models import Attribute, PriceTier, Product
from apps.catalog.tests.factories import (
    AttributeFactory,
    CategoryFactory,
    ProductFactory,
    VariantFactory,
)
from apps.core.management.commands.setup_roles import Command as SetupRoles
from apps.core.roles import INVENTORY_MANAGER, ORDER_MANAGER
from apps.inventory import services as stock
from apps.inventory.models import Lot, StockMovement
from apps.orders import workflow
from apps.orders.models import Order
from apps.orders.tests.factories import make_order
from apps.shipping.models import ShippingSettings

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture
def owner():
    return User.objects.create_superuser("owner", "o@example.com", "pass")


def staff(*codenames, role=None, username="staff"):
    user = User.objects.create_user(username, password="pass-1234", is_staff=True)
    user.user_permissions.add(*Permission.objects.filter(codename__in=codenames))
    if role:
        SetupRoles().handle()
        user.groups.add(Group.objects.get(name=role))
    return User.objects.get(pk=user.pk)  # Fresh permission cache.


def png(name="photo.png"):
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(buffer, "PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


# Access ---------------------------------------------------------------------------------


def test_anonymous_goes_to_portal_login(client):
    response = client.get(reverse("portal:order_list"))
    assert response.status_code == 302
    assert response["Location"].startswith(reverse("portal:login"))


def test_customer_cannot_log_in_to_portal(client):
    User.objects.create_user("+923001234567", password="pass-1234")
    response = client.post(
        reverse("portal:login"), {"username": "+923001234567", "password": "pass-1234"}
    )
    assert response.status_code == 200
    assert "not a staff account" in response.content.decode()


def test_staff_logs_in_and_sees_only_their_menu(client):
    staff(role=ORDER_MANAGER)
    response = client.post(
        reverse("portal:login"), {"username": "staff", "password": "pass-1234"}, follow=True
    )
    content = response.content.decode()
    assert response.status_code == 200
    assert reverse("portal:order_list") in content
    assert reverse("portal:wholesale_list") in content
    assert reverse("portal:lot_list") not in content
    assert reverse("portal:staff_list") not in content


def test_role_permissions_are_enforced(client):
    client.force_login(staff(role=ORDER_MANAGER))
    assert client.get(reverse("portal:order_list")).status_code == 200
    assert client.get(reverse("portal:lot_list")).status_code == 403
    assert client.get(reverse("portal:product_add")).status_code == 403
    assert client.get(reverse("portal:staff_list")).status_code == 403
    assert client.get(reverse("portal:settings")).status_code == 403


def test_admin_is_owner_only(client, owner):
    client.force_login(staff(role=INVENTORY_MANAGER))
    assert client.get(reverse("admin:index")).status_code == 302
    client.force_login(owner)
    assert client.get(reverse("admin:index")).status_code == 200


@pytest.mark.parametrize(
    "name",
    [
        "dashboard",
        "order_list",
        "wholesale_list",
        "blockedphone_list",
        "blockedphone_add",
        "product_list",
        "product_add",
        "category_list",
        "category_add",
        "attribute_list",
        "attribute_add",
        "brand_list",
        "stock_list",
        "stock_near_empty",
        "stock_out",
        "movement_list",
        "lot_list",
        "lot_add",
        "import_csv",
        "settings",
        "city_list",
        "page_list",
        "staff_list",
        "staff_add",
        "activity",
    ],
)
def test_owner_pages_load(client, owner, name):
    VariantFactory()
    client.force_login(owner)
    assert client.get(reverse(f"portal:{name}")).status_code == 200


# Catalog --------------------------------------------------------------------------------


def product_post(category, **extra):
    data = {
        "title": "Rolex style watch",
        "category": category.pk,
        "condition": "new",
        "is_active": "on",
        "advance_value": 0,
        "variants-TOTAL_FORMS": "1",
        "variants-INITIAL_FORMS": "0",
        "variants-MIN_NUM_FORMS": "1",
        "variants-MAX_NUM_FORMS": "1000",
        "variants-0-sku": "W-1",
        "variants-0-price": "4500",
        "variants-0-min_order_qty": "1",
        "variants-0-order_step": "1",
        "variants-0-track_stock": "on",
        "variants-0-is_active": "on",
        "variants-0-add_stock": "3",
        "images-TOTAL_FORMS": "0",
        "images-INITIAL_FORMS": "0",
        "images-MIN_NUM_FORMS": "0",
        "images-MAX_NUM_FORMS": "1000",
    }
    data.update(extra)
    return data


def test_inventory_manager_adds_product_with_photos_attributes_and_stock(client):
    user = staff(role=INVENTORY_MANAGER)
    client.force_login(user)
    category = CategoryFactory(name="Watches")
    strap = AttributeFactory(name="Strap", type=Attribute.CHOICE, choices="Metal\nLeather")
    strap.categories.add(category)
    lot = Lot.objects.create(reference="DXB-1")
    data = product_post(category, **{f"attr_{strap.pk}": "Metal", "stock_lot": lot.pk})
    data["images"] = [png("a.png"), png("b.png")]
    response = client.post(reverse("portal:product_add"), data)
    assert response.status_code == 302, response.context and response.context["form"].errors
    product = Product.objects.get()
    variant = product.variants.get()
    assert product.attribute_values() == [(strap, "Metal")]
    assert product.images.count() == 2
    assert variant.stock_on_hand == 3
    movement = StockMovement.objects.get()
    assert movement.user == user and movement.lot == lot
    # It is in stock, so customers see it.
    assert client.get(product.get_absolute_url()).status_code == 200


def test_category_change_reloads_attribute_fields(client, owner):
    client.force_login(owner)
    category = CategoryFactory()
    size = AttributeFactory(name="Size")
    size.categories.add(category)
    response = client.get(
        reverse("portal:product_attributes"), {"category": category.pk}, HTTP_HX_REQUEST="true"
    )
    assert f'name="attr_{size.pk}"' in response.content.decode()


def test_staff_without_price_permission_cannot_change_price(client):
    client.force_login(staff(role=INVENTORY_MANAGER))
    variant = VariantFactory(price=1000, sku="P-1")
    product = variant.product
    data = product_post(
        product.category,
        title=product.title,
        **{
            "variants-INITIAL_FORMS": "1",
            "variants-0-id": variant.pk,
            "variants-0-sku": "P-1",
            "variants-0-price": "1",
            "variants-0-add_stock": "",
        },
    )
    assert client.post(reverse("portal:product_edit", args=[product.pk]), data).status_code == 302
    variant.refresh_from_db()
    assert variant.price == 1000  # The price field is locked.

    tiers = {
        "action": "tiers",
        "tiers-TOTAL_FORMS": "1",
        "tiers-INITIAL_FORMS": "0",
        "tiers-MIN_NUM_FORMS": "0",
        "tiers-MAX_NUM_FORMS": "1000",
        "tiers-0-min_quantity": "10",
        "tiers-0-unit_price": "800",
    }
    url = reverse("portal:variant_detail", args=[variant.pk])
    assert client.post(url, tiers).status_code == 403


def test_owner_sets_bulk_prices(client, owner):
    client.force_login(owner)
    variant = VariantFactory(price=1000)
    data = {
        "action": "tiers",
        "tiers-TOTAL_FORMS": "2",
        "tiers-INITIAL_FORMS": "0",
        "tiers-MIN_NUM_FORMS": "0",
        "tiers-MAX_NUM_FORMS": "1000",
        "tiers-0-min_quantity": "10",
        "tiers-0-unit_price": "900",
        "tiers-1-min_quantity": "50",
        "tiers-1-unit_price": "750",
        "tiers-1-wholesale_only": "on",
    }
    response = client.post(reverse("portal:variant_detail", args=[variant.pk]), data)
    assert response.status_code == 302
    assert list(PriceTier.objects.values_list("min_quantity", "wholesale_only")) == [
        (10, False),
        (50, True),
    ]


def test_staff_cannot_delete_products(client):
    client.force_login(staff(role=INVENTORY_MANAGER))
    product = ProductFactory()
    response = client.post(reverse("portal:product_delete", args=[product.pk]))
    assert response.status_code == 403
    assert Product.objects.filter(pk=product.pk).exists()


def test_owner_cannot_delete_product_with_stock_history(client, owner):
    client.force_login(owner)
    variant = VariantFactory()
    stock.receive(variant, 1)
    client.post(reverse("portal:product_delete", args=[variant.product_id]))
    assert Product.objects.filter(pk=variant.product_id).exists()
    empty = ProductFactory()
    client.post(reverse("portal:product_delete", args=[empty.pk]))
    assert not Product.objects.filter(pk=empty.pk).exists()


# Stock ----------------------------------------------------------------------------------


def stock_post(kind, quantity, **extra):
    return {"action": "stock", "kind": kind, "quantity": quantity, **extra}


def test_receive_stock_on_variant_page(client):
    user = staff("view_variant", "add_stockmovement")
    client.force_login(user)
    variant = VariantFactory()
    lot = Lot.objects.create(reference="L1")
    url = reverse("portal:variant_detail", args=[variant.pk])
    response = client.post(url, stock_post("received", 4, lot=lot.pk))
    assert response.status_code == 302
    variant.refresh_from_db()
    assert variant.stock_on_hand == 4
    assert StockMovement.objects.get().user == user


def test_adjust_needs_permission(client):
    client.force_login(staff("view_variant", "add_stockmovement"))
    variant = VariantFactory()
    url = reverse("portal:variant_detail", args=[variant.pk])
    response = client.post(url, stock_post("adjustment", 4, note="count"))
    assert response.status_code == 200
    assert "permission to adjust" in response.content.decode()
    variant.refresh_from_db()
    assert variant.stock_on_hand == 0


def test_lot_cost_needs_permission(client):
    lot = Lot.objects.create(reference="L2", total_cost=50000)
    url = reverse("portal:lot_edit", args=[lot.pk])
    client.force_login(staff("view_lot", "change_lot"))
    assert 'name="total_cost"' not in client.get(url).content.decode()
    client.force_login(staff("view_lot", "change_lot", "view_cost_and_profit", username="boss"))
    assert 'name="total_cost"' in client.get(url).content.decode()


def test_near_empty_and_out_of_stock_views_and_alert(client):
    client.force_login(staff("view_variant"))
    low = VariantFactory(sku="LOW-1")
    stock.receive(low, 1)
    ok = VariantFactory(sku="OK-1")
    stock.receive(ok, 50)
    own = VariantFactory(sku="OWN-1", low_stock_threshold=60)  # Its own level.
    stock.receive(own, 50)
    VariantFactory(sku="OUT-1")

    content = client.get(reverse("portal:stock_near_empty")).content.decode()
    assert "LOW-1" in content and "OWN-1" in content
    assert "OK-1" not in content and "OUT-1" not in content
    content = client.get(reverse("portal:stock_out")).content.decode()
    assert "OUT-1" in content and "LOW-1" not in content

    response = client.get(reverse("portal:dashboard"))
    assert response.context["stock_alert_count"] == 2
    assert 'id="stock-alerts"' in response.content.decode()

    settings_row = ShippingSettings.load()
    settings_row.low_stock_default = 0
    settings_row.save()
    assert client.get(reverse("portal:dashboard")).context["stock_alert_count"] == 1


# Orders ---------------------------------------------------------------------------------


def test_order_manager_confirms_and_ships_order(client):
    user = staff(role=ORDER_MANAGER)
    client.force_login(user)
    variant = VariantFactory(price=1000)
    order = make_order([(variant, 1)])
    detail = reverse("portal:order_detail", args=[order.pk])
    content = client.get(detail).content.decode()
    assert f"tel:{order.phone}" in content
    assert "wa.me/" in content

    client.post(reverse("portal:order_transition", args=[order.pk, Order.CONFIRMED]))
    order.refresh_from_db()
    assert order.status == Order.CONFIRMED

    ship = reverse("portal:order_transition", args=[order.pk, Order.SHIPPED])
    response = client.post(ship, {"courier": ""}, follow=True)
    assert "Enter the courier" in response.content.decode()
    client.post(ship, {"courier": "TCS", "tracking_number": "123"})
    order.refresh_from_db()
    assert order.status == Order.SHIPPED
    assert order.status_history.first().user == user


def test_advance_must_be_received_before_confirm(client):
    client.force_login(staff(role=ORDER_MANAGER))
    order = make_order([(VariantFactory(price=1000), 1)])
    Order.objects.filter(pk=order.pk).update(
        advance_status=Order.ADVANCE_PENDING, advance_amount=500
    )
    confirm = reverse("portal:order_transition", args=[order.pk, Order.CONFIRMED])
    client.post(confirm)
    order.refresh_from_db()
    assert order.status == Order.PENDING
    client.post(reverse("portal:order_advance", args=[order.pk]), {"note": "Bank app"})
    client.post(confirm)
    order.refresh_from_db()
    assert order.advance_status == Order.ADVANCE_RECEIVED
    assert order.status == Order.CONFIRMED


def test_staff_edits_address_until_dispatch(client, owner):
    client.force_login(staff(role=ORDER_MANAGER))
    order = make_order([(VariantFactory(price=1000), 1)])
    data = {
        "full_name": "Ali Raza",
        "phone": "0300 1234567",
        "city": order.city_id,
        "address": "House 2, Street 5",
        "staff_notes": "Call after 5pm",
    }
    client.post(reverse("portal:order_detail", args=[order.pk]), data)
    order.refresh_from_db()
    assert order.address == "House 2, Street 5"
    assert order.staff_notes == "Call after 5pm"

    workflow.transition(order, Order.CONFIRMED, user=owner)
    workflow.transition(order, Order.SHIPPED, user=owner, courier="TCS")
    data.update(address="Somewhere else", staff_notes="Shipped")
    client.post(reverse("portal:order_detail", args=[order.pk]), data)
    order.refresh_from_db()
    assert order.address == "House 2, Street 5"
    assert order.staff_notes == "Shipped"


def test_dashboard_numbers(client, owner):
    variant = VariantFactory(price=1000)
    stock.receive(variant, 3, cost_per_unit=400)
    order = make_order([(variant, 2)])
    make_order([(VariantFactory(price=500), 1)], phone="+923111234567")
    workflow.transition(order, Order.CONFIRMED, user=owner)
    workflow.transition(order, Order.SHIPPED, user=owner, courier="TCS")
    workflow.transition(order, Order.DELIVERED, user=owner)
    client.force_login(owner)
    n = client.get(reverse("portal:dashboard")).context["n"]
    assert n["to_confirm"] == 1
    assert n["cod_pending"] == order.total
    assert n["profit_month"] == 2000 - 800
    assert n["low_stock"] == 1


def test_dashboard_hides_profit_without_permission(client):
    client.force_login(staff("view_order"))
    assert "profit_month" not in client.get(reverse("portal:dashboard")).context["n"]


# Owner ----------------------------------------------------------------------------------


def test_owner_creates_staff_account_with_role(client, owner):
    SetupRoles().handle()
    client.force_login(owner)
    group = Group.objects.get(name=INVENTORY_MANAGER)
    extra = Permission.objects.get(codename="change_price")
    response = client.post(
        reverse("portal:staff_add"),
        {
            "username": "sara",
            "first_name": "Sara",
            "password": "strong-pass-123",
            "is_active": "on",
            "groups": [group.pk],
            "user_permissions": [extra.pk],
        },
    )
    assert response.status_code == 302
    sara = User.objects.get(username="sara")
    assert sara.is_staff and not sara.is_superuser
    assert sara.check_password("strong-pass-123")
    assert sara.has_perm("catalog.add_product") and sara.has_perm("catalog.change_price")


def test_staff_activity_is_owner_only_and_shows_changes(client, owner):
    client.force_login(staff(role=INVENTORY_MANAGER))
    assert client.get(reverse("portal:activity")).status_code == 403
    client.force_login(owner)
    category = CategoryFactory()
    client.post(
        reverse("portal:category_edit", args=[category.pk]),
        {"name": "Renamed", "sort_order": 0, "advance_type": "none", "advance_value": 0},
    )
    content = client.get(reverse("portal:activity"), {"user": owner.pk}).content.decode()
    assert "-&gt; Renamed" in content


def test_settings_save(client, owner):
    client.force_login(owner)
    data = {
        "default_delivery_fee": 300,
        "default_cod_fee": 50,
        "bulky_item_fee": 0,
        "advance_percent_above_total": 0,
        "advance_payment_details": "Meezan Bank 0123",
        "low_stock_default": 3,
    }
    assert client.post(reverse("portal:settings"), data).status_code == 302
    settings_row = ShippingSettings.load()
    assert settings_row.default_delivery_fee == 300
    assert settings_row.low_stock_default == 3
