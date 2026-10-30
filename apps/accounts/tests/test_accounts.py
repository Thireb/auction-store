import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse

from apps.accounts.models import WholesaleProfile
from apps.catalog.models import PriceTier
from apps.catalog.tests.factories import VariantFactory
from apps.inventory import services as stock
from apps.orders.tests.factories import make_order

pytestmark = pytest.mark.django_db


@pytest.fixture
def buyer():
    return get_user_model().objects.create_user(
        "+923001234567", password="a-Strong-pass-42", first_name="Ali Khan"
    )


def test_login_with_any_phone_format(client, buyer):
    response = client.post(
        reverse("accounts:login"), {"username": "0300-1234567", "password": "a-Strong-pass-42"}
    )
    assert response.status_code == 302
    assert int(client.session["_auth_user_id"]) == buyer.pk


def test_signup(client):
    response = client.post(
        reverse("accounts:signup"),
        {"full_name": "Sara", "phone": "03111234567", "password": "a-Strong-pass-42"},
    )
    assert response.url == reverse("accounts:account")
    assert get_user_model().objects.filter(username="+923111234567").exists()


def test_signup_refuses_existing_number(client, buyer):
    response = client.post(
        reverse("accounts:signup"),
        {"full_name": "Ali", "phone": "03001234567", "password": "a-Strong-pass-42"},
    )
    assert "exists" in response.content.decode()


def test_account_lists_only_own_orders(client, buyer):
    own = make_order([(VariantFactory(), 1)])
    own.user = buyer
    own.save()
    other = make_order([(VariantFactory(), 1)], phone="+923211234567")
    client.force_login(buyer)
    content = client.get(reverse("accounts:account")).content.decode()
    assert own.number in content and other.number not in content
    assert client.get(reverse("accounts:order", args=[other.number])).status_code == 404
    assert client.get(reverse("accounts:order", args=[own.number])).status_code == 200


def test_account_needs_login(client):
    assert reverse("accounts:login") in client.get(reverse("accounts:account")).url


def test_track_order_with_number_and_phone(client):
    order = make_order([(VariantFactory(), 1)])
    response = client.get(reverse("track_order"), {"number": order.number, "phone": "0300 1234567"})
    assert "Pending confirmation" in response.content.decode()
    response = client.get(reverse("track_order"), {"number": order.number, "phone": "0399 1234567"})
    assert "could not find" in response.content.decode()


def test_wholesale_application_and_approval(client, buyer):
    client.force_login(buyer)
    client.post(reverse("accounts:account"), {"business_name": "Ali Mobiles", "city": "Lahore"})
    profile = WholesaleProfile.objects.get(user=buyer)
    assert profile.status == WholesaleProfile.PENDING

    staff = get_user_model().objects.create_user("staff", password="x", is_staff=True)
    staff.user_permissions.add(
        *Permission.objects.filter(
            codename__in=["change_wholesaleprofile", "view_wholesaleprofile"]
        )
    )
    client.force_login(staff)
    url = reverse("admin:accounts_wholesaleprofile_changelist")
    client.post(url, {"action": "approve", "_selected_action": [profile.pk]})
    profile.refresh_from_db()
    assert profile.status == WholesaleProfile.PENDING  # No approve permission yet.

    staff.user_permissions.add(Permission.objects.get(codename="approve_wholesale_buyer"))
    client.post(url, {"action": "approve", "_selected_action": [profile.pk]})
    profile.refresh_from_db()
    assert profile.is_approved and profile.reviewed_by == staff


def test_approved_buyer_gets_wholesale_price_in_cart(client, buyer):
    variant = VariantFactory(price=1000)
    stock.receive(variant, 500)
    PriceTier.objects.create(variant=variant, min_quantity=100, unit_price=700, wholesale_only=True)
    WholesaleProfile.objects.create(
        user=buyer, business_name="Shop", city="Lahore", status=WholesaleProfile.APPROVED
    )
    client.force_login(buyer)
    client.post(reverse("cart:add"), {"variant": variant.pk, "quantity": 100})
    assert "Rs 70,000" in client.get(reverse("cart:detail")).content.decode()
