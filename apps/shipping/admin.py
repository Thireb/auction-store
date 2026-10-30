from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import City, ShippingSettings


@admin.register(ShippingSettings)
class ShippingSettingsAdmin(SimpleHistoryAdmin):
    fieldsets = [
        (
            "Delivery",
            {
                "fields": [
                    "default_delivery_fee",
                    "default_cod_fee",
                    "free_delivery_above",
                    "bulky_item_fee",
                ]
            },
        ),
        (
            "Advance payment",
            {
                "fields": [
                    "advance_above_total",
                    "advance_percent_above_total",
                    "advance_payment_details",
                ],
                "description": "Set advances for single products or categories on them.",
            },
        ),
    ]

    def has_add_permission(self, request):
        return not ShippingSettings.objects.exists() and super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        from django.shortcuts import redirect

        obj = ShippingSettings.load()
        return redirect("admin:shipping_shippingsettings_change", obj.pk)


@admin.register(City)
class CityAdmin(SimpleHistoryAdmin):
    list_display = [
        "name",
        "province",
        "is_active",
        "cod_allowed",
        "delivery_fee",
        "cod_fee",
        "estimated_days",
        "sort_order",
    ]
    list_editable = [
        "is_active",
        "cod_allowed",
        "delivery_fee",
        "cod_fee",
        "estimated_days",
        "sort_order",
    ]
    list_filter = ["province", "is_active", "cod_allowed"]
    search_fields = ["name"]

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
