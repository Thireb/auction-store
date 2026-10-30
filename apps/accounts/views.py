from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import get_object_or_404, redirect, render

from apps.orders.models import Order

from .forms import PhoneLoginForm, SignupForm, TrackOrderForm, WholesaleForm


class PhoneLoginView(LoginView):
    form_class = PhoneLoginForm
    template_name = "accounts/login.html"


def signup(request):
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(request, "Your account is ready.")
        return redirect("accounts:account")
    return render(request, "accounts/signup.html", {"form": form})


@login_required
def account(request):
    profile = getattr(request.user, "wholesale_profile", None)
    form = None if profile else WholesaleForm(request.POST or None)
    if form and request.method == "POST" and form.is_valid():
        profile = form.save(commit=False)
        profile.user = request.user
        profile.save()
        messages.success(request, "Thank you. We will review your wholesale request.")
        return redirect("accounts:account")
    context = {
        "orders": request.user.orders.all()[:50],
        "profile": profile,
        "wholesale_form": form,
    }
    return render(request, "accounts/account.html", context)


@login_required
def order_detail(request, number):
    order = get_object_or_404(
        Order.objects.prefetch_related("items", "shipments"), number=number, user=request.user
    )
    return render(request, "accounts/order_detail.html", {"order": order})


def track_order(request):
    form = TrackOrderForm(request.GET or None)
    order = None
    if form.is_bound and form.is_valid():
        order = (
            Order.objects.prefetch_related("items", "shipments")
            .filter(
                number__iexact=form.cleaned_data["number"].strip(), phone=form.cleaned_data["phone"]
            )
            .first()
        )
        if order is None:
            form.add_error(None, "We could not find an order with this number and phone.")
    return render(request, "accounts/track.html", {"form": form, "order": order})
