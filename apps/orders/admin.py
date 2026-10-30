from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from simple_history.admin import SimpleHistoryAdmin

from . import workflow
from .models import BlockedPhone, Order, OrderItem, OrderStatusHistory, Shipment
from .notifications import order_whatsapp_url


class ReadOnlyInline(admin.TabularInline):
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class OrderItemInline(ReadOnlyInline):
    model = OrderItem
    fields = ["product_title", "variant_name", "sku", "unit_price", "quantity", "line_total"]
    readonly_fields = fields


class StatusHistoryInline(ReadOnlyInline):
    model = OrderStatusHistory
    fields = ["created_at", "from_status", "to_status", "user", "note"]
    readonly_fields = fields


class ShipmentInline(ReadOnlyInline):
    model = Shipment
    fields = ["booked_at", "courier", "tracking_number"]
    readonly_fields = fields


class TransitionForm(forms.Form):
    note = forms.CharField(
        required=False, max_length=200, widget=forms.TextInput(attrs={"size": 60})
    )
    courier = forms.CharField(required=False, max_length=60)
    tracking_number = forms.CharField(required=False, max_length=80)


@admin.register(Order)
class OrderAdmin(SimpleHistoryAdmin):
    change_form_template = "admin/orders/order/change_form.html"
    list_display = [
        "number",
        "created_at",
        "full_name",
        "phone_display",
        "city_name",
        "total",
        "advance_status",
        "status",
    ]
    list_filter = ["status", "advance_status", "city", "created_at"]
    search_fields = ["number", "full_name", "phone", "address"]
    date_hierarchy = "created_at"
    inlines = [OrderItemInline, ShipmentInline, StatusHistoryInline]
    actions = ["confirm_orders", "pack_orders"]
    fieldsets = [
        (None, {"fields": ["number", "status", "created_at", "contact"]}),
        (
            "Customer",
            {"fields": ["full_name", "phone", "email", "city", "address", "landmark", "user"]},
        ),
        ("Notes", {"fields": ["customer_notes", "staff_notes"]}),
        (
            "Money",
            {
                "fields": [
                    "subtotal",
                    "delivery_fee",
                    "cod_fee",
                    "total",
                    "advance_amount",
                    "advance_status",
                    "advance_proof_link",
                    "cod_amount",
                ]
            },
        ),
        (
            "Other",
            {
                "fields": ["ip_address", "confirmed_at", "shipped_at", "delivered_at"],
                "classes": ["collapse"],
            },
        ),
    ]
    readonly_fields = [
        "number",
        "status",
        "created_at",
        "contact",
        "user",
        "customer_notes",
        "subtotal",
        "delivery_fee",
        "cod_fee",
        "total",
        "advance_amount",
        "advance_status",
        "advance_proof_link",
        "cod_amount",
        "ip_address",
        "confirmed_at",
        "shipped_at",
        "delivered_at",
    ]

    def get_readonly_fields(self, request, obj=None):
        fields = list(self.readonly_fields)
        if obj and obj.status not in workflow.RESERVED_STATUSES:
            # The parcel has left: the address on it cannot change any more.
            fields += ["full_name", "phone", "email", "city", "address", "landmark"]
        return fields

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    @admin.display(description="Contact")
    def contact(self, obj):
        return format_html(
            '<a href="tel:{}">Call {}</a> &nbsp;|&nbsp; '
            '<a href="{}" target="_blank" rel="noopener">WhatsApp</a>',
            obj.phone,
            obj.phone_display,
            order_whatsapp_url(obj),
        )

    @admin.display(description="Phone")
    def phone_display(self, obj):
        return obj.phone_display

    @admin.display(description="Payment proof")
    def advance_proof_link(self, obj):
        if obj.advance_proof:
            return format_html(
                '<a href="{}" target="_blank">Open screenshot</a>', obj.advance_proof.url
            )
        return "-"

    @admin.display(description="Cash to collect")
    def cod_amount(self, obj):
        return f"Rs {obj.cod_amount:,}"

    # Status buttons -----------------------------------------------------------------

    def get_urls(self):
        view = self.admin_site.admin_view
        return [
            path(
                "<int:pk>/status/<str:target>/",
                view(self.transition_view),
                name="orders_order_transition",
            ),
            path(
                "<int:pk>/advance-received/", view(self.advance_view), name="orders_order_advance"
            ),
            path("<int:pk>/print/", view(self.print_view), name="orders_order_print"),
        ] + super().get_urls()

    def change_view(self, request, object_id, form_url="", extra_context=None):
        order = self.get_object(request, object_id)
        extra_context = extra_context or {}
        if order:
            labels = dict(Order.STATUS_CHOICES)
            extra_context["transitions"] = [
                (
                    target,
                    labels[target],
                    reverse("admin:orders_order_transition", args=[order.pk, target]),
                )
                for target in workflow.allowed_transitions(order, request.user)
            ]
            extra_context["can_mark_advance"] = (
                order.advance_status == Order.ADVANCE_PENDING
                and request.user.has_perm("orders.change_order")
            )
        return super().change_view(request, object_id, form_url, extra_context)

    def transition_view(self, request, pk, target):
        order = get_object_or_404(Order, pk=pk)
        if target not in dict(Order.STATUS_CHOICES):
            raise PermissionDenied
        form = TransitionForm(request.POST if request.method == "POST" else None)
        if request.method == "POST" and form.is_valid():
            try:
                workflow.transition(order, target, user=request.user, **form.cleaned_data)
            except workflow.TransitionError as exc:
                form.add_error(None, str(exc))
            else:
                self.message_user(
                    request, f"Order {order.number} is now {dict(Order.STATUS_CHOICES)[target]}."
                )
                return redirect("admin:orders_order_change", order.pk)
        context = {
            **self.admin_site.each_context(request),
            "title": f"Order {order.number}: {dict(Order.STATUS_CHOICES)[target]}",
            "order": order,
            "target": target,
            "form": form,
            "opts": self.model._meta,
            "needs_courier": target == Order.SHIPPED,
        }
        return TemplateResponse(request, "admin/orders/order/transition.html", context)

    def advance_view(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        if request.method != "POST":
            return redirect("admin:orders_order_change", order.pk)
        try:
            workflow.mark_advance_received(order, user=request.user)
        except workflow.TransitionError as exc:
            self.message_user(request, str(exc), messages.ERROR)
        else:
            self.message_user(request, "Advance marked as received.")
        return redirect("admin:orders_order_change", order.pk)

    def print_view(self, request, pk):
        if not request.user.has_perm("orders.view_order"):
            raise PermissionDenied
        order = get_object_or_404(Order.objects.prefetch_related("items"), pk=pk)
        return TemplateResponse(request, "admin/orders/order/print.html", {"order": order})

    # Bulk actions -------------------------------------------------------------------

    def _bulk(self, request, queryset, target):
        done, failed = 0, []
        for order in queryset:
            try:
                workflow.transition(order, target, user=request.user, note="Bulk action")
                done += 1
            except (workflow.TransitionError, PermissionDenied) as exc:
                failed.append(f"{order.number}: {exc}")
        if done:
            self.message_user(request, f"{done} orders updated.")
        for message in failed:
            self.message_user(request, message, messages.WARNING)

    @admin.action(description="Mark selected orders as confirmed", permissions=["change"])
    def confirm_orders(self, request, queryset):
        self._bulk(request, queryset, Order.CONFIRMED)

    @admin.action(description="Mark selected orders as packed", permissions=["change"])
    def pack_orders(self, request, queryset):
        self._bulk(request, queryset, Order.PACKED)


@admin.register(BlockedPhone)
class BlockedPhoneAdmin(admin.ModelAdmin):
    list_display = ["phone", "reason", "created_at"]
    search_fields = ["phone", "reason"]
