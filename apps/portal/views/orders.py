from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.models import WholesaleProfile
from apps.accounts.services import APPROVE_PERM, review_wholesale
from apps.orders import workflow
from apps.orders.models import Order
from apps.orders.notifications import order_whatsapp_url
from apps.shipping.models import City

from ..access import portal_view
from ..forms import OrderEditForm, TransitionForm
from ..history import object_history

PAGE_SIZE = 50
STATUS_LABELS = dict(Order.STATUS_CHOICES)


@portal_view("orders.view_order")
def order_list(request):
    orders = Order.objects.select_related("city")
    counts = dict(Order.objects.values_list("status").annotate(n=Count("pk")))
    status = request.GET.get("status", "")
    if status == "open":
        orders = orders.filter(status__in=Order.OPEN_STATUSES)
    elif status == "to_dispatch":
        orders = orders.filter(status__in=[Order.CONFIRMED, Order.PACKED])
    elif status in STATUS_LABELS:
        orders = orders.filter(status=status)
    advance = request.GET.get("advance", "")
    if advance in dict(Order.ADVANCE_STATUS_CHOICES):
        orders = orders.filter(advance_status=advance)
    city = request.GET.get("city", "")
    if city.isdigit():
        orders = orders.filter(city_id=city)
    q = request.GET.get("q", "").strip()
    if q:
        orders = orders.filter(
            Q(number__icontains=q)
            | Q(full_name__icontains=q)
            | Q(phone__icontains=q.lstrip("0"))
            | Q(address__icontains=q)
        )
    page = Paginator(orders, PAGE_SIZE).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    tabs = [("", "All", sum(counts.values()))] + [
        (key, label, counts.get(key, 0)) for key, label in Order.STATUS_CHOICES
    ]
    context = {
        "page_obj": page,
        "query_string": query.urlencode(),
        "tabs": tabs,
        "status": status,
        "advance": advance,
        "advance_choices": Order.ADVANCE_STATUS_CHOICES,
        "city": city,
        "cities": City.objects.filter(orders__isnull=False).distinct(),
        "q": q,
    }
    return render(request, "portal/orders/order_list.html", context)


def _order_context(request, order, edit_form=None, transition_errors=None):
    user = request.user
    locked = order.status not in workflow.RESERVED_STATUSES
    if edit_form is None:
        edit_form = OrderEditForm(instance=order, address_locked=locked)
    if not user.has_perm("orders.change_order"):
        for field in edit_form.fields.values():
            field.disabled = True
    transitions = [
        (target, STATUS_LABELS[target]) for target in workflow.allowed_transitions(order, user)
    ]
    return {
        "order": order,
        "title": f"Order {order.number}",
        "items": order.items.all(),
        "shipments": order.shipments.all(),
        "status_history": order.status_history.select_related("user"),
        "whatsapp_url": order_whatsapp_url(order),
        "edit_form": edit_form,
        "transitions": transitions,
        "transition_form": TransitionForm(),
        "transition_errors": transition_errors or {},
        "can_change": user.has_perm("orders.change_order"),
        "can_mark_advance": order.advance_status == Order.ADVANCE_PENDING
        and user.has_perm("orders.change_order"),
        "can_block": user.has_perm("orders.add_blockedphone"),
        "other_orders": Order.objects.filter(phone=order.phone).exclude(pk=order.pk)[:10],
        "history": object_history(order, limit=15),
    }


@portal_view("orders.view_order")
def order_detail(request, pk):
    order = get_object_or_404(Order.objects.select_related("city", "user"), pk=pk)
    edit_form = None
    if request.method == "POST":
        if not request.user.has_perm("orders.change_order"):
            raise PermissionDenied
        locked = order.status not in workflow.RESERVED_STATUSES
        edit_form = OrderEditForm(request.POST, instance=order, address_locked=locked)
        if edit_form.is_valid():
            edit_form.save()
            messages.success(request, "Order details saved.")
            return redirect("portal:order_detail", pk)
    context = _order_context(request, order, edit_form)
    return render(request, "portal/orders/order_detail.html", context)


@require_POST
@portal_view("orders.change_order")
def order_transition(request, pk, target):
    order = get_object_or_404(Order, pk=pk)
    if target not in STATUS_LABELS:
        raise PermissionDenied
    form = TransitionForm(request.POST)
    if form.is_valid():
        try:
            workflow.transition(order, target, user=request.user, **form.cleaned_data)
        except workflow.TransitionError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"Order {order.number} is now {STATUS_LABELS[target]}.")
    return redirect("portal:order_detail", pk)


@require_POST
@portal_view("orders.change_order")
def order_advance(request, pk):
    order = get_object_or_404(Order, pk=pk)
    try:
        workflow.mark_advance_received(order, user=request.user, note=request.POST.get("note", ""))
    except workflow.TransitionError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Advance marked as received. You can confirm the order now.")
    return redirect("portal:order_detail", pk)


@portal_view("orders.view_order")
def order_print(request, pk):
    order = get_object_or_404(Order.objects.prefetch_related("items"), pk=pk)
    return render(request, "portal/orders/print.html", {"order": order})


@portal_view("accounts.view_wholesaleprofile")
def wholesale_list(request):
    profiles = WholesaleProfile.objects.select_related("user", "reviewed_by")
    status = request.GET.get("status", WholesaleProfile.PENDING)
    if status in dict(WholesaleProfile.STATUS_CHOICES):
        profiles = profiles.filter(status=status)
    q = request.GET.get("q", "").strip()
    if q:
        profiles = profiles.filter(
            Q(business_name__icontains=q)
            | Q(user__username__icontains=q)
            | Q(user__first_name__icontains=q)
            | Q(city__icontains=q)
        )
    counts = dict(WholesaleProfile.objects.values_list("status").annotate(n=Count("pk")))
    context = {
        "profiles": profiles[:200],
        "status": status,
        "tabs": [(k, v, counts.get(k, 0)) for k, v in WholesaleProfile.STATUS_CHOICES]
        + [("all", "All", sum(counts.values()))],
        "q": q,
        "can_review": request.user.has_perm(APPROVE_PERM),
        "title": "Wholesale buyers",
    }
    return render(request, "portal/orders/wholesale_list.html", context)


@require_POST
@portal_view("accounts.view_wholesaleprofile")
def wholesale_review(request, pk, status):
    profile = get_object_or_404(WholesaleProfile, pk=pk)
    try:
        review_wholesale(profile, status, user=request.user)
    except ValueError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"{profile.business_name}: {profile.get_status_display()}.")
    return redirect("portal:wholesale_list")
