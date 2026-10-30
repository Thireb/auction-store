from django import forms
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.urls import path
from django.utils.html import format_html
from simple_history.admin import SimpleHistoryAdmin

from .importer import import_csv, template_csv
from .models import (
    Attribute,
    Brand,
    Category,
    PriceTier,
    Product,
    ProductAttributeValue,
    ProductImage,
    Variant,
)

ATTR_PREFIX = "attr_"


class OwnerDeleteMixin:
    """Only the owner (a superuser) can delete. Staff hide things with "is active"."""

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(Category)
class CategoryAdmin(OwnerDeleteMixin, SimpleHistoryAdmin):
    list_display = ["__str__", "is_active", "sort_order", "product_count"]
    list_editable = ["is_active", "sort_order"]
    list_filter = ["is_active", "parent"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ["name"]}
    autocomplete_fields = ["parent"]

    @admin.display(description="Products")
    def product_count(self, obj):
        return obj.products.count()


@admin.register(Attribute)
class AttributeAdmin(OwnerDeleteMixin, SimpleHistoryAdmin):
    list_display = ["name", "type", "unit", "is_filterable", "category_list", "sort_order"]
    list_editable = ["sort_order"]
    list_filter = ["type", "is_filterable", "categories"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ["name"]}
    filter_horizontal = ["categories"]

    @admin.display(description="Categories")
    def category_list(self, obj):
        return ", ".join(c.name for c in obj.categories.all())


@admin.register(Brand)
class BrandAdmin(OwnerDeleteMixin, admin.ModelAdmin):
    list_display = ["name", "is_active"]
    list_editable = ["is_active"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ["name"]}


PRICE_PERM = "catalog.change_price"


class PriceLockedForm(forms.ModelForm):
    """Staff without the change_price permission set prices on new variants only."""

    user = None
    price_fields = ("price", "compare_at_price")

    def clean(self):
        data = super().clean()
        if self.instance.pk and self.user and not self.user.has_perm(PRICE_PERM):
            for name in self.price_fields:
                if name in self.changed_data:
                    self.add_error(name, "You do not have permission to change prices.")
        return data


def with_user(form_class, user):
    return type(form_class.__name__, (form_class,), {"user": user})


class VariantInline(admin.TabularInline):
    model = Variant
    form = PriceLockedForm
    extra = 0
    min_num = 1
    fields = [
        "sku",
        "name",
        "price",
        "compare_at_price",
        "min_order_qty",
        "order_step",
        "weight_grams",
        "track_stock",
        "stock_on_hand",
        "stock_reserved",
        "is_active",
        "sort_order",
    ]
    readonly_fields = ["stock_on_hand", "stock_reserved"]
    show_change_link = True

    def get_formset(self, request, obj=None, **kwargs):
        kwargs["form"] = with_user(self.form, request.user)
        return super().get_formset(request, obj, **kwargs)


class PriceTierInline(admin.TabularInline):
    model = PriceTier
    extra = 1
    fields = ["min_quantity", "unit_price", "wholesale_only"]

    def _can_edit(self, request):
        return request.user.has_perm(PRICE_PERM)

    def has_add_permission(self, request, obj=None):
        return self._can_edit(request)

    def has_change_permission(self, request, obj=None):
        return self._can_edit(request)

    def has_delete_permission(self, request, obj=None):
        return self._can_edit(request)

    def has_view_permission(self, request, obj=None):
        return True


class LowStockFilter(admin.SimpleListFilter):
    title = "stock"
    parameter_name = "stock"

    def lookups(self, request, model_admin):
        return [("low", "Near empty"), ("out", "Out of stock")]

    def queryset(self, request, queryset):
        from apps.inventory import levels

        if self.value() == "low":
            return levels.near_empty(queryset)
        if self.value() == "out":
            return levels.out_of_stock(queryset)
        return None


@admin.register(Variant)
class VariantAdmin(OwnerDeleteMixin, SimpleHistoryAdmin):
    """The stock view: every variant with its stock numbers."""

    list_display = [
        "sku",
        "__str__",
        "price",
        "stock_on_hand",
        "stock_reserved",
        "available",
        "low_stock_threshold",
        "is_active",
    ]
    list_filter = [LowStockFilter, "is_active", "track_stock", "product__category"]
    search_fields = ["sku", "name", "product__title"]
    list_select_related = ["product"]
    readonly_fields = ["stock_on_hand", "stock_reserved"]
    autocomplete_fields = ["product"]
    form = PriceLockedForm
    inlines = [PriceTierInline]

    def get_form(self, request, obj=None, **kwargs):
        kwargs["form"] = with_user(self.form, request.user)
        return super().get_form(request, obj, **kwargs)

    @admin.display(description="Available")
    def available(self, obj):
        return obj.stock_available if obj.track_stock else "-"


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ["preview", "image", "alt_text", "sort_order"]
    readonly_fields = ["preview"]

    @admin.display(description="")
    def preview(self, obj):
        if obj.pk and obj.image:
            return format_html('<img src="{}" style="height:60px">', obj.image.url)
        return ""


class ProductAdminForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = "__all__"  # noqa: DJ007 - the admin fieldsets choose the fields

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            saved = {v.attribute_id: v.value for v in self.instance.attribute_values_set.all()}
            for name in self.fields:
                if name.startswith(ATTR_PREFIX):
                    self.fields[name].initial = saved.get(int(name[len(ATTR_PREFIX) :]), "")

    def save_attribute_values(self, product):
        for name, value in self.cleaned_data.items():
            if not name.startswith(ATTR_PREFIX):
                continue
            attribute_id = int(name[len(ATTR_PREFIX) :])
            text = "" if value is None else str(value).strip()
            if text:
                ProductAttributeValue.objects.update_or_create(
                    product=product, attribute_id=attribute_id, defaults={"value": text}
                )
            else:
                ProductAttributeValue.objects.filter(
                    product=product, attribute_id=attribute_id
                ).delete()


class ImportForm(forms.Form):
    file = forms.FileField(label="CSV file")
    dry_run = forms.BooleanField(label="Check only (do not save)", required=False, initial=True)


@admin.register(Product)
class ProductAdmin(OwnerDeleteMixin, SimpleHistoryAdmin):
    form = ProductAdminForm
    change_list_template = "admin/catalog/product/change_list.html"
    list_display = ["title", "category", "brand", "condition", "price", "is_active", "is_featured"]
    list_editable = ["is_active", "is_featured"]
    list_filter = ["is_active", "is_featured", "condition", "category", "brand"]
    search_fields = ["title", "description", "variants__sku"]
    autocomplete_fields = ["category", "brand"]
    prepopulated_fields = {"slug": ["title"]}
    inlines = [VariantInline, ProductImageInline]
    actions = ["make_active", "make_hidden", "make_featured"]
    list_select_related = ["category", "brand"]

    base_fieldsets = [
        (None, {"fields": ["title", "slug", "category", "brand", "condition", "description"]}),
        ("Store", {"fields": ["is_active", "is_featured", "origin_note"]}),
        (
            "Delivery and advance",
            {
                "fields": ["is_bulky", "advance_type", "advance_value"],
                "classes": ["collapse"],
                "description": "Leave empty to use the category settings.",
            },
        ),
    ]

    def _attributes(self, obj):
        return list(obj.category.all_attributes()) if obj and obj.category_id else []

    def get_fieldsets(self, request, obj=None):
        fieldsets = list(self.base_fieldsets)
        attributes = self._attributes(obj)
        if attributes:
            names = [f"{ATTR_PREFIX}{a.pk}" for a in attributes]
            fieldsets.append(("Attributes", {"fields": names}))
        elif obj is None:
            fieldsets.append(
                (
                    "Attributes",
                    {
                        "fields": [],
                        "description": "Save first. The attributes of the category then show here.",
                    },
                )
            )
        return fieldsets

    def get_form(self, request, obj=None, change=False, **kwargs):
        extra = {f"{ATTR_PREFIX}{a.pk}": a.form_field() for a in self._attributes(obj)}
        kwargs["form"] = type("ProductAdminFormWithAttributes", (self.form,), extra)
        return super().get_form(request, obj, change=change, **kwargs)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        form.save_attribute_values(form.instance)

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("variants")

    def get_urls(self):
        custom = [
            path(
                "import/",
                self.admin_site.admin_view(self.import_view),
                name="catalog_product_import",
            )
        ]
        return custom + super().get_urls()

    def import_view(self, request):
        if not (
            self.has_add_permission(request)
            and request.user.has_perm("inventory.add_stockmovement")
        ):
            raise PermissionDenied
        if request.GET.get("template"):
            response = HttpResponse(template_csv(), content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="products-template.csv"'
            return response
        result, dry_run = None, True
        form = ImportForm(request.POST or None, request.FILES or None)
        if request.method == "POST" and form.is_valid():
            dry_run = form.cleaned_data["dry_run"]
            result = import_csv(form.cleaned_data["file"], request.user, dry_run=dry_run)
            if result.ok and not dry_run:
                self.message_user(
                    request,
                    f"Imported {result.products_created} products, "
                    f"{result.variants_created} variants and {result.stock_rows} stock rows.",
                )
        context = {
            **self.admin_site.each_context(request),
            "title": "Import CSV",
            "form": form,
            "result": result,
            "dry_run": dry_run,
            "opts": self.model._meta,
        }
        return TemplateResponse(request, "admin/catalog/product/import.html", context)

    @admin.display(description="Price")
    def price(self, obj):
        price = obj.min_price
        return f"Rs {price:,}" if price is not None else "-"

    @admin.action(description="Show selected products in the store")
    def make_active(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description="Hide selected products from the store")
    def make_hidden(self, request, queryset):
        queryset.update(is_active=False)

    @admin.action(description="Mark selected products as featured")
    def make_featured(self, request, queryset):
        queryset.update(is_featured=True)
