from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.forms import modelform_factory
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy

from apps.shipping.models import ShippingSettings

from ..access import is_portal_user, portal_view
from ..dashboard import dashboard_numbers
from ..forms import StaffForm, StyledFormMixin
from ..history import activity, object_history


class PortalLoginForm(StyledFormMixin, AuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not is_portal_user(user):
            raise ValidationError("This account is not a staff account.", code="not_staff")


class PortalLoginView(LoginView):
    form_class = PortalLoginForm
    template_name = "portal/login.html"
    next_page = reverse_lazy("portal:dashboard")


@portal_view()
def dashboard(request):
    user = request.user
    context = {
        "title": "Dashboard",
        "n": dashboard_numbers(user),
        "show_orders": user.has_perm("orders.view_order"),
        "show_stock": user.has_perm("catalog.view_variant"),
        "show_wholesale": user.has_perm("accounts.view_wholesaleprofile"),
    }
    return render(request, "portal/dashboard.html", context)


def _formfield(field, **kwargs):
    """A link typed without "https://" gets it (the Django 6 default)."""
    if isinstance(field, models.URLField):
        kwargs["assume_scheme"] = "https"
    return field.formfield(**kwargs)


@portal_view("shipping.change_shippingsettings")
def settings_view(request):
    obj = ShippingSettings.load()
    form_class = modelform_factory(
        ShippingSettings,
        form=type("SettingsForm", (StyledFormMixin, forms.ModelForm), {}),
        formfield_callback=_formfield,
        fields=[
            "default_delivery_fee",
            "default_cod_fee",
            "free_delivery_above",
            "bulky_item_fee",
            "advance_above_total",
            "advance_percent_above_total",
            "advance_payment_details",
            "whatsapp_channel_url",
            "low_stock_default",
        ],
    )
    form = form_class(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Delivery and payment settings saved.")
        return redirect("portal:settings")
    context = {
        "title": "Store settings",
        "form": form,
        "history": object_history(obj, limit=10),
    }
    return render(request, "portal/owner/settings.html", context)


def _staff_users():
    return get_user_model().objects.filter(Q(is_staff=True) | Q(is_superuser=True))


@portal_view(owner=True)
def staff_list(request):
    users = _staff_users().prefetch_related("groups").order_by("-is_active", "username")
    return render(request, "portal/owner/staff_list.html", {"users": users, "title": "Staff"})


@portal_view(owner=True)
def staff_edit(request, pk=None):
    account = get_object_or_404(_staff_users(), pk=pk) if pk else None
    form = StaffForm(request.POST or None, instance=account)
    if request.method == "POST" and form.is_valid():
        account = form.save()
        messages.success(request, f"Saved staff account “{account.username}”.")
        return redirect("portal:staff_list")
    context = {
        "title": account.username if account else "New staff account",
        "form": form,
        "account": account,
    }
    return render(request, "portal/owner/staff_form.html", context)


@portal_view(owner=True)
def activity_view(request):
    user_id = request.GET.get("user", "")
    user_id = int(user_id) if user_id.isdigit() else None
    try:
        days = min(max(int(request.GET.get("days", 7)), 1), 90)
    except ValueError:
        days = 7
    context = {
        "title": "Staff activity",
        "rows": activity(user_id, days),
        "staff": _staff_users().order_by("username"),
        "selected_user": user_id,
        "days": days,
    }
    return render(request, "portal/owner/activity.html", context)
