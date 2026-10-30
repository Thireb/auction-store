import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied

from apps.catalog.tests.factories import VariantFactory
from apps.inventory import services
from apps.inventory.models import Lot, StockItem, StockMovement

pytestmark = pytest.mark.django_db


@pytest.fixture
def variant():
    return VariantFactory()


@pytest.fixture
def stock_admin():
    user = get_user_model().objects.create_user("stock", password="x")
    user.user_permissions.add(Permission.objects.get(codename="adjust_stock"))
    return get_user_model().objects.get(pk=user.pk)


def test_receive_adds_stock_per_lot(variant):
    lot = Lot.objects.create(reference="DXB-1")
    services.receive(variant, 5, lot=lot, cost_per_unit=300)
    services.receive(variant, 3, lot=lot)
    variant.refresh_from_db()
    assert variant.stock_on_hand == 8
    item = StockItem.objects.get(variant=variant, lot=lot)
    assert (item.quantity_received, item.quantity_on_hand, item.cost_per_unit) == (8, 8, 300)
    assert StockMovement.objects.filter(variant=variant, kind="received").count() == 2


def test_reserve_and_release(variant):
    services.receive(variant, 2)
    services.reserve(variant, 2, reference="AS-1")
    variant.refresh_from_db()
    assert variant.stock_available == 0
    with pytest.raises(services.InsufficientStock):
        services.reserve(variant, 1)
    services.release(variant, 2, reference="AS-1")
    variant.refresh_from_db()
    assert (variant.stock_on_hand, variant.stock_reserved) == (2, 0)


def test_release_never_goes_below_zero(variant):
    services.receive(variant, 1)
    services.reserve(variant, 1)
    services.release(variant, 5)
    variant.refresh_from_db()
    assert variant.stock_reserved == 0


def test_dispatch_takes_oldest_lot_first(variant):
    old, new = Lot.objects.create(reference="OLD"), Lot.objects.create(reference="NEW")
    services.receive(variant, 2, lot=old, cost_per_unit=100)
    services.receive(variant, 5, lot=new, cost_per_unit=150)
    services.reserve(variant, 4)
    taken = services.dispatch(variant, 4, reference="AS-2")
    assert taken == [(old, 2, 100), (new, 2, 150)]
    variant.refresh_from_db()
    assert (variant.stock_on_hand, variant.stock_reserved) == (3, 0)
    assert StockItem.objects.get(lot=old).quantity_on_hand == 0
    assert StockItem.objects.get(lot=new).quantity_on_hand == 3


def test_return_to_stock(variant):
    services.receive(variant, 1)
    services.reserve(variant, 1)
    services.dispatch(variant, 1)
    services.return_to_stock(variant, 1, reference="AS-3", note="Customer refused")
    variant.refresh_from_db()
    assert variant.stock_available == 1


def test_untracked_variant_is_always_available():
    variant = VariantFactory(track_stock=False)
    services.reserve(variant, 100)
    variant.refresh_from_db()
    assert variant.stock_reserved == 0
    assert variant.in_stock


def test_adjust_needs_permission_and_note(variant, stock_admin):
    plain = get_user_model().objects.create_user("plain", password="x")
    with pytest.raises(PermissionDenied):
        services.adjust(variant, 1, user=plain, note="count")
    with pytest.raises(ValueError):
        services.adjust(variant, 1, user=stock_admin, note="")
    services.adjust(variant, 3, user=stock_admin, note="Found in store room")
    services.adjust(variant, -1, user=stock_admin, note="Damaged")
    variant.refresh_from_db()
    assert variant.stock_on_hand == 2
    movement = StockMovement.objects.filter(kind="adjustment").first()
    assert movement.user == stock_admin
    assert movement.on_hand_after == 2


def test_adjust_cannot_remove_more_than_on_hand(variant, stock_admin):
    services.receive(variant, 1)
    with pytest.raises(services.InsufficientStock):
        services.adjust(variant, -2, user=stock_admin, note="Lost")


def test_quantity_must_be_positive(variant):
    with pytest.raises(ValueError):
        services.receive(variant, 0)
