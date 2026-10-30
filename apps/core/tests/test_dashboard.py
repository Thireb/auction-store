import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse

from apps.catalog.tests.factories import VariantFactory
from apps.orders import workflow
from apps.orders.models import Order
from apps.orders.tests.factories import make_order

pytestmark = pytest.mark.django_db


@pytest.fixture
def owner():
    return get_user_model().objects.create_superuser("owner", "o@x.com", "x")


def test_dashboard_numbers(client, owner):
    from apps.inventory import services as stock

    variant = VariantFactory(price=1000)
    stock.receive(variant, 3, cost_per_unit=400)
    order = make_order([(variant, 2)])
    make_order([(VariantFactory(price=500), 1)], phone="+923111234567")
    workflow.transition(order, Order.CONFIRMED, user=owner)
    workflow.transition(order, Order.SHIPPED, user=owner, courier="TCS")
    workflow.transition(order, Order.DELIVERED, user=owner)
    client.force_login(owner)
    response = client.get(reverse("admin_dashboard"))
    n = response.context["n"]
    assert n["to_confirm"] == 1
    assert n["cod_pending"] == order.total
    assert n["profit_month"] == 2000 - 800
    assert n["low_stock"] == 1


def test_dashboard_hides_profit_without_permission(client):
    staff = get_user_model().objects.create_user("s", password="x", is_staff=True)
    staff.user_permissions.add(Permission.objects.get(codename="view_order"))
    client.force_login(staff)
    response = client.get(reverse("admin_dashboard"))
    assert "profit_month" not in response.context["n"]


def test_staff_activity_is_owner_only(client, owner):
    staff = get_user_model().objects.create_user("s", password="x", is_staff=True)
    client.force_login(staff)
    assert client.get(reverse("admin_staff_activity")).status_code == 403


def test_staff_activity_shows_admin_changes(client, owner):
    client.force_login(owner)
    variant = VariantFactory(price=1000)
    post = {
        "product": variant.product.pk,
        "sku": variant.sku,
        "price": "1200",
        "min_order_qty": 1,
        "order_step": 1,
        "low_stock_threshold": 2,
        "is_active": "on",
        "track_stock": "on",
        "sort_order": 0,
        "price_tiers-TOTAL_FORMS": "0",
        "price_tiers-INITIAL_FORMS": "0",
        "price_tiers-MIN_NUM_FORMS": "0",
        "price_tiers-MAX_NUM_FORMS": "1000",
    }
    client.post(reverse("admin:catalog_variant_change", args=[variant.pk]), post)
    response = client.get(reverse("admin_staff_activity"), {"user": owner.pk, "days": 1})
    content = response.content.decode()
    assert "price: 1000 -&gt; 1200" in content


def test_admin_index_has_links(client, owner):
    client.force_login(owner)
    content = client.get(reverse("admin:index")).content.decode()
    assert reverse("admin_dashboard") in content
    assert reverse("admin_staff_activity") in content
