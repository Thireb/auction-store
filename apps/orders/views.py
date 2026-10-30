from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.cart.cart import Cart
from apps.shipping.models import City, ShippingSettings

from . import services
from .forms import AdvanceProofForm, CheckoutForm
from .models import Order

RECENT_ORDERS_KEY = "recent_orders"


def client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    return forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")


def _initial(user):
    if not (user and user.is_authenticated):
        return {}
    last = user.orders.order_by("-created_at").first()
    initial = {"full_name": user.get_full_name(), "phone": user.username, "email": user.email}
    if last:
        initial.update({"city": last.city_id, "address": last.address, "landmark": last.landmark})
    return initial


def checkout(request):
    cart = Cart(request)
    if not cart.lines:
        return redirect("cart:detail")
    if cart.has_errors:
        messages.error(request, "Some items in your cart need a change before checkout.")
        return redirect("cart:detail")

    if request.htmx and request.method == "GET":
        city = City.objects.filter(pk=request.GET.get("city") or None, is_active=True).first()
        context = {"cart": cart, "totals": services.summarize(cart, city)}
        return render(request, "orders/partials/order_summary.html", context)

    form = CheckoutForm(request.POST or None, user=request.user, initial=_initial(request.user))
    city = None
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        user = request.user if request.user.is_authenticated else None
        if data.get("create_account"):
            user = get_user_model().objects.create_user(
                username=data["phone"],
                email=data.get("email", ""),
                password=data["password"],
                first_name=data["full_name"][:150],
            )
        try:
            order = services.place_order(
                cart, data, user=user, ip_address=client_ip(request), request=request
            )
        except services.CheckoutError as exc:
            if data.get("create_account") and user:
                user.delete()
            form.add_error(None, str(exc))
        else:
            if data.get("create_account"):
                login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            request.session[RECENT_ORDERS_KEY] = [
                order.number,
                *request.session.get(RECENT_ORDERS_KEY, [])[:9],
            ]
            return redirect(order.get_thanks_url())
    if form.is_bound:
        city = form.cleaned_data.get("city") if hasattr(form, "cleaned_data") else None
    elif form.initial.get("city"):
        city = City.objects.filter(pk=form.initial["city"]).first()
    context = {"form": form, "cart": cart, "totals": services.summarize(cart, city)}
    return render(request, "orders/checkout.html", context)


def _recent_order(request, number):
    if number not in request.session.get(RECENT_ORDERS_KEY, []):
        raise Http404
    return get_object_or_404(Order.objects.prefetch_related("items"), number=number)


def thanks(request, number):
    order = _recent_order(request, number)
    context = {
        "order": order,
        "proof_form": AdvanceProofForm(),
        "payment_details": ShippingSettings.load().advance_payment_details,
    }
    return render(request, "orders/thanks.html", context)


@require_POST
def upload_advance_proof(request, number):
    order = _recent_order(request, number)
    if order.advance_status != Order.ADVANCE_PENDING:
        return redirect(order.get_thanks_url())
    form = AdvanceProofForm(request.POST, request.FILES, instance=order)
    if form.is_valid():
        form.save()
        messages.success(request, "Thank you. We will check your payment and call you.")
        return redirect(order.get_thanks_url())
    context = {
        "order": order,
        "proof_form": form,
        "payment_details": ShippingSettings.load().advance_payment_details,
    }
    return render(request, "orders/thanks.html", context, status=400)
