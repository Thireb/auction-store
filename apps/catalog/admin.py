from django import forms
from django.contrib import admin
from django.utils.html import format_html
from simple_history.admin import SimpleHistoryAdmin

from .models import (
    Attribute,
    Brand,
    Category,
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


class VariantInline(admin.TabularInline):
    model = Variant
    extra = 0
    min_num = 1
    fields = ["sku", "name", "price", "compare_at_price", "weight_grams", "is_active", "sort_order"]


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


@admin.register(Product)
class ProductAdmin(OwnerDeleteMixin, SimpleHistoryAdmin):
    form = ProductAdminForm
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
