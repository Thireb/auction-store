from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import BlockedPhone, Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    fields = ["product_title", "variant_name", "sku", "unit_price", "quantity", "line_total"]
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(SimpleHistoryAdmin):
    list_display = ["number", "created_at", "full_name", "phone", "city_name", "total", "status"]
    list_filter = ["status", "advance_status", "city", "created_at"]
    search_fields = ["number", "full_name", "phone", "address"]
    date_hierarchy = "created_at"
    inlines = [OrderItemInline]
    readonly_fields = [
        "number",
        "user",
        "subtotal",
        "delivery_fee",
        "cod_fee",
        "total",
        "advance_amount",
        "ip_address",
        "created_at",
        "updated_at",
    ]

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(BlockedPhone)
class BlockedPhoneAdmin(admin.ModelAdmin):
    list_display = ["phone", "reason", "created_at"]
    search_fields = ["phone", "reason"]
