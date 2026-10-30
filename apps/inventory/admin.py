from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError

from apps.catalog.models import MONEY

from . import services
from .models import Lot, StockItem, StockMovement

COST_PERM = "inventory.view_cost_and_profit"


class StockItemInline(admin.TabularInline):
    model = StockItem
    extra = 0
    can_delete = False
    fields = ["variant", "quantity_received", "quantity_on_hand", "cost_per_unit"]
    readonly_fields = fields

    def get_fields(self, request, obj=None):
        if request.user.has_perm(COST_PERM):
            return self.fields
        return [f for f in self.fields if f != "cost_per_unit"]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Lot)
class LotAdmin(admin.ModelAdmin):
    list_display = ["reference", "source", "purchase_date", "units_received", "units_on_hand"]
    search_fields = ["reference", "source", "notes"]
    date_hierarchy = "purchase_date"
    inlines = [StockItemInline]
    cost_fields = ["total_cost", "landed_cost"]

    def get_fields(self, request, obj=None):
        fields = ["reference", "source", "purchase_date", "total_cost", "landed_cost", "notes"]
        if request.user.has_perm(COST_PERM):
            return fields
        return [f for f in fields if f not in self.cost_fields]

    def get_list_display(self, request):
        if request.user.has_perm(COST_PERM):
            return [*self.list_display, "total_cost", "landed_cost"]
        return self.list_display

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    @admin.display(description="Units received")
    def units_received(self, obj):
        return sum(i.quantity_received for i in obj.stock_items.all())

    @admin.display(description="Units on hand")
    def units_on_hand(self, obj):
        return sum(i.quantity_on_hand for i in obj.stock_items.all())

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("stock_items")


class StockChangeForm(forms.ModelForm):
    """Receive new stock, or adjust stock by hand. Saved through the stock services."""

    KIND_CHOICES = [
        (StockMovement.RECEIVED, "Receive new stock"),
        (StockMovement.ADJUSTMENT, "Manual adjustment (+ or -)"),
    ]
    kind = forms.ChoiceField(choices=KIND_CHOICES)
    cost_per_unit = forms.DecimalField(
        required=False,
        max_digits=MONEY["max_digits"],
        decimal_places=0,
        min_value=0,
        help_text="Only for received stock.",
    )

    class Meta:
        model = StockMovement
        fields = ["variant", "kind", "quantity", "lot", "cost_per_unit", "note"]
        help_texts = {"quantity": "For an adjustment, use a negative number to remove stock."}

    def clean(self):
        data = super().clean()
        kind, qty = data.get("kind"), data.get("quantity")
        if qty is not None:
            if kind == StockMovement.RECEIVED and qty <= 0:
                raise ValidationError({"quantity": "Received quantity must be more than 0."})
            if kind == StockMovement.ADJUSTMENT and qty == 0:
                raise ValidationError({"quantity": "The change cannot be 0."})
        if kind == StockMovement.ADJUSTMENT:
            if not self.user.has_perm("inventory.adjust_stock"):
                raise ValidationError({"kind": "You do not have permission to adjust stock."})
            if not data.get("note"):
                raise ValidationError({"note": "Write a reason for the adjustment."})
            variant = data.get("variant")
            if variant and qty is not None and qty < 0 and -qty > variant.stock_on_hand:
                raise ValidationError(
                    {"quantity": f"Only {variant.stock_on_hand} on hand. You cannot remove {-qty}."}
                )
        return data


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = [
        "created_at",
        "variant",
        "kind",
        "quantity",
        "on_hand_after",
        "reserved_after",
        "lot",
        "reference",
        "user",
    ]
    list_filter = ["kind", "created_at", "user", "lot"]
    search_fields = ["variant__sku", "variant__product__title", "reference", "note"]
    autocomplete_fields = ["variant", "lot"]
    date_hierarchy = "created_at"
    list_select_related = ["variant__product", "lot", "user"]

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs["form"] = type(
                "StockChangeFormForUser", (StockChangeForm,), {"user": request.user}
            )
            if not request.user.has_perm(COST_PERM):
                kwargs["fields"] = ["variant", "kind", "quantity", "lot", "note"]
        return super().get_form(request, obj, **kwargs)

    def get_fields(self, request, obj=None):
        if obj is None:
            fields = ["variant", "kind", "quantity", "lot", "cost_per_unit", "note"]
            if not request.user.has_perm(COST_PERM):
                fields.remove("cost_per_unit")
            return fields
        return [f for f in self.list_display if f != "created_at"] + ["note", "created_at"]

    def get_readonly_fields(self, request, obj=None):
        return self.get_fields(request, obj) if obj else []

    def save_model(self, request, obj, form, change):
        data = form.cleaned_data
        if data["kind"] == StockMovement.RECEIVED:
            services.receive(
                data["variant"],
                data["quantity"],
                lot=data.get("lot"),
                cost_per_unit=data.get("cost_per_unit"),
                user=request.user,
                note=data.get("note", ""),
            )
        else:
            services.adjust(data["variant"], data["quantity"], user=request.user, note=data["note"])
        # The service created the movement; point the admin at it for the log and redirect.
        saved = StockMovement.objects.filter(variant=data["variant"]).latest("pk")
        obj.pk = saved.pk
        obj.__dict__.update({k: v for k, v in saved.__dict__.items() if not k.startswith("_")})

    def has_change_permission(self, request, obj=None):
        return False if obj else super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False
