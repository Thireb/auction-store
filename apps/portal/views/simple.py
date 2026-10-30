from django import forms
from django.db.models import Count, Sum

from apps.catalog.models import Attribute, Brand, Category
from apps.core.models import Page
from apps.core.phone import normalize_pk_mobile
from apps.inventory.models import Lot
from apps.orders.models import BlockedPhone
from apps.shipping.models import City

from ..forms import COST_PERM, StyledFormMixin
from .crud import Crud


class CategoryCrud(Crud):
    model = Category
    name = "category"
    fields = [
        "name",
        "parent",
        "description",
        "image",
        "sort_order",
        "is_active",
        "is_bulky",
        "advance_type",
        "advance_value",
    ]
    columns = [
        ("Category", str),
        ("Products", lambda c: c.n_products),
        ("Sort", "sort_order"),
        ("Active", "is_active"),
        ("Bulky", "is_bulky"),
    ]
    search_fields = ["name", "description"]
    filters = ["is_active", "is_bulky"]
    owner_delete = True
    help_text = (
        "A category can sit inside another one. Products in a sub-category also show in "
        "its parents. Attributes of a parent apply to its sub-categories."
    )

    def get_queryset(self, request):
        return Category.objects.select_related("parent__parent").annotate(
            n_products=Count("products")
        )


class AttributeForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Attribute
        fields = ["name", "type", "choices", "unit", "categories", "is_filterable", "sort_order"]
        widgets = {"categories": forms.SelectMultiple(attrs={"size": 10})}


class AttributeCrud(Crud):
    model = Attribute
    name = "attribute"
    form_class = AttributeForm
    fields = AttributeForm.Meta.fields
    columns = [
        ("Name", str),
        ("Type", "type"),
        ("Categories", lambda a: ", ".join(c.name for c in a.categories.all())),
        ("Filter", "is_filterable"),
        ("Sort", "sort_order"),
    ]
    search_fields = ["name"]
    filters = ["type", "is_filterable"]
    owner_delete = True
    help_text = (
        "An attribute is a product detail such as size or colour. Link it to categories: "
        "products in them get a field for it, and the store shows it as a filter."
    )

    def get_queryset(self, request):
        return Attribute.objects.prefetch_related("categories")


class BrandCrud(Crud):
    model = Brand
    name = "brand"
    fields = ["name", "is_active"]
    columns = [("Name", "name"), ("Active", "is_active")]
    search_fields = ["name"]
    filters = ["is_active"]
    owner_delete = True


class LotCrud(Crud):
    model = Lot
    name = "lot"
    columns = [
        ("Reference", "reference"),
        ("Source", "source"),
        ("Purchase date", "purchase_date"),
        ("Pieces received", lambda lot: lot.n_received or 0),
        ("Pieces on hand", lambda lot: lot.n_on_hand or 0),
    ]
    search_fields = ["reference", "source", "notes"]
    owner_delete = True
    help_text = "A lot is one purchase from an auction or an exporter. Stock is received into lots."

    def get_queryset(self, request):
        return Lot.objects.annotate(
            n_received=Sum("stock_items__quantity_received"),
            n_on_hand=Sum("stock_items__quantity_on_hand"),
        )

    def get_fields(self, request, obj=None):
        fields = ["reference", "source", "purchase_date", "total_cost", "landed_cost", "notes"]
        if request.user.has_perm(COST_PERM):
            return fields
        return [f for f in fields if f not in ("total_cost", "landed_cost")]

    def get_form_class(self, request, obj=None):
        form = super().get_form_class(request, obj)
        if "purchase_date" in form.base_fields:
            form.base_fields["purchase_date"].widget = forms.DateInput(
                attrs={"type": "date", "class": "w-full border rounded px-2 py-1 bg-white"}
            )
        return form

    def edit_context(self, request, obj):
        return {
            "stock_items": obj.stock_items.select_related("variant__product"),
            "show_cost": request.user.has_perm(COST_PERM),
        }


class CityCrud(Crud):
    model = City
    name = "city"
    fields = [
        "name",
        "province",
        "is_active",
        "cod_allowed",
        "delivery_fee",
        "cod_fee",
        "estimated_days",
        "sort_order",
    ]
    columns = [
        ("City", "name"),
        ("Province", "province"),
        ("Delivery", "is_active"),
        ("COD", "cod_allowed"),
        ("Delivery fee", lambda c: "default" if c.delivery_fee is None else c.delivery_fee),
        ("COD fee", lambda c: "default" if c.cod_fee is None else c.cod_fee),
        ("Days", "estimated_days"),
    ]
    search_fields = ["name"]
    filters = ["province", "is_active", "cod_allowed"]
    owner_delete = True


class PageCrud(Crud):
    model = Page
    name = "page"
    fields = ["title", "slug", "body", "show_in_footer", "is_active", "sort_order"]
    columns = [("Title", "title"), ("Footer", "show_in_footer"), ("Active", "is_active")]
    search_fields = ["title", "body"]
    owner_delete = True

    def get_form_class(self, request, obj=None):
        form = super().get_form_class(request, obj)
        form.base_fields["body"].widget.attrs["rows"] = 12
        form.base_fields["slug"].required = False
        return form


class BlockedPhoneForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = BlockedPhone
        fields = ["phone", "reason"]

    def clean_phone(self):
        return normalize_pk_mobile(self.cleaned_data["phone"])


class BlockedPhoneCrud(Crud):
    model = BlockedPhone
    name = "blockedphone"
    form_class = BlockedPhoneForm
    fields = BlockedPhoneForm.Meta.fields
    columns = [("Phone", str), ("Reason", "reason"), ("Since", "created_at")]
    search_fields = ["phone", "reason"]
    owner_delete = True
    help_text = "These phone numbers cannot place orders."


CRUDS = {
    "categories": CategoryCrud(),
    "attributes": AttributeCrud(),
    "brands": BrandCrud(),
    "lots": LotCrud(),
    "cities": CityCrud(),
    "pages": PageCrud(),
    "blocked-phones": BlockedPhoneCrud(),
}
