import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied

from apps.catalog.tests.factories import VariantFactory
from apps.inventory import services as stock
from apps.orders import workflow
from apps.orders.models import Order

from .factories import make_order

pytestmark = pytest.mark.django_db


def staff(*codenames):
    name = "-".join(codenames)
    user = get_user_model().objects.create_user(name, password="x", is_staff=True)
    user.user_permissions.add(*Permission.objects.filter(codename__in=codenames))
    return get_user_model().objects.get(pk=user.pk)


@pytest.fixture
def manager():
    return staff("change_order", "view_order")


@pytest.fixture
def variant():
    v = VariantFactory(price=1000)
    stock.receive(v, 5, cost_per_unit=600)
    return v


def test_happy_path_moves_stock_and_logs_history(manager, variant):
    order = make_order([(variant, 2)])
    for target in [Order.CONFIRMED, Order.PACKED]:
        order = workflow.transition(order, target, user=manager)
    variant.refresh_from_db()
    assert (variant.stock_on_hand, variant.stock_reserved) == (5, 2)

    order = workflow.transition(
        order, Order.SHIPPED, user=manager, courier="TCS", tracking_number="T1"
    )
    variant.refresh_from_db()
    assert (variant.stock_on_hand, variant.stock_reserved) == (3, 0)
    assert order.shipments.get().tracking_number == "T1"
    assert order.items.get().cost_total == 1200
    assert order.shipped_at is not None

    order = workflow.transition(order, Order.DELIVERED, user=manager)
    order = workflow.transition(order, Order.COMPLETED, user=manager)
    history = list(order.status_history.values_list("to_status", flat=True))
    assert history[0] == Order.COMPLETED
    assert history[-1] == Order.PENDING  # "Order placed"


def test_cancel_releases_stock(manager, variant):
    order = make_order([(variant, 2)])
    workflow.transition(order, Order.CANCELLED, user=manager, note="Customer changed mind")
    variant.refresh_from_db()
    assert variant.stock_reserved == 0


def test_cancel_after_confirmation_needs_permission(manager, variant):
    order = workflow.transition(make_order([(variant, 1)]), Order.CONFIRMED, user=manager)
    assert Order.CANCELLED not in workflow.allowed_transitions(order, manager)
    with pytest.raises(PermissionDenied):
        workflow.transition(order, Order.CANCELLED, user=manager)
    boss = staff("change_order", "cancel_confirmed_order")
    workflow.transition(order, Order.CANCELLED, user=boss)


def test_refused_parcel_returns_stock(manager, variant):
    order = make_order([(variant, 1)])
    order = workflow.transition(order, Order.CONFIRMED, user=manager)
    order = workflow.transition(order, Order.SHIPPED, user=manager, courier="Leopards")
    workflow.transition(order, Order.RETURNED, user=manager, note="Refused at door")
    variant.refresh_from_db()
    assert (variant.stock_on_hand, variant.stock_reserved) == (5, 0)


def test_invalid_jumps_are_refused(manager, variant):
    order = make_order([(variant, 1)])
    with pytest.raises(workflow.TransitionError):
        workflow.transition(order, Order.DELIVERED, user=manager)
    order = workflow.transition(order, Order.CONFIRMED, user=manager)
    with pytest.raises(workflow.TransitionError, match="courier"):
        workflow.transition(order, Order.SHIPPED, user=manager)


def test_advance_must_be_received_before_confirmation(manager, variant):
    order = make_order([(variant, 1)])
    Order.objects.filter(pk=order.pk).update(
        advance_amount=200, advance_status=Order.ADVANCE_PENDING
    )
    order.refresh_from_db()
    assert Order.AWAITING_ADVANCE in workflow.allowed_transitions(order, manager)
    order = workflow.transition(order, Order.AWAITING_ADVANCE, user=manager)
    with pytest.raises(workflow.TransitionError, match="advance"):
        workflow.transition(order, Order.CONFIRMED, user=manager)
    order = workflow.mark_advance_received(order, user=manager)
    order = workflow.transition(order, Order.CONFIRMED, user=manager)
    assert order.cod_amount == order.total - 200


def test_user_without_change_permission_cannot_move_orders(variant):
    viewer = staff("view_order")
    order = make_order([(variant, 1)])
    assert workflow.allowed_transitions(order, viewer) == []
    with pytest.raises(PermissionDenied):
        workflow.transition(order, Order.CONFIRMED, user=viewer)
