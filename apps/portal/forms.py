from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory, modelformset_factory
from django.urls import reverse

from apps.catalog.models import (
    Category,
    PriceTier,
    Product,
    ProductAttributeValue,
    ProductImage,
    Variant,
)
from apps.core.phone import normalize_pk_mobile
from apps.inventory.models import Lot, StockMovement
from apps.orders.models import Order
from apps.shipping.models import City

INPUT = "w-full border rounded px-2 py-1 bg-white"
CHECK = "h-4 w-4"
PRICE_PERM = "catalog.change_price"
COST_PERM = "inventory.view_cost_and_profit"
ATTR_PREFIX = "attr_"


def style_form(form):
    for field in form.fields.values():
        widget = field.widget
        if isinstance(widget, forms.CheckboxSelectMultiple | forms.RadioSelect):
            continue
        css = CHECK if isinstance(widget, forms.CheckboxInput) else INPUT
        widget.attrs.setdefault("class", css)
        if isinstance(widget, forms.Textarea) and str(widget.attrs.get("rows")) == "10":
            widget.attrs["rows"] = 3  # Django's default of 10 rows is too tall here.
    return form


class StyledFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_form(self)


# Catalog -------------------------------------------------------------------------------


class ProductForm(StyledFormMixin, forms.ModelForm):
    """The product with one field for each attribute of its category (and parents)."""

    class Meta:
        model = Product
        fields = [
            "title",
            "category",
            "brand",
            "condition",
            "description",
            "origin_note",
            "is_active",
            "is_featured",
            "is_bulky",
            "advance_type",
            "advance_value",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, category=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.filter(is_active=True)
        # Changing the category reloads the attribute fields (HTMX).
        url = reverse("portal:product_attributes")
        self.fields["category"].widget.attrs.update(
            {
                "hx-get": f"{url}?product={self.instance.pk or ''}",
                "hx-target": "#attribute-fields",
                "hx-swap": "outerHTML",
            }
        )
        category = category or (self.instance.category if self.instance.category_id else None)
        self.attributes = list(category.all_attributes()) if category else []
        saved = {}
        if self.instance.pk:
            saved = {v.attribute_id: v.value for v in self.instance.attribute_values_set.all()}
        for attribute in self.attributes:
            field = attribute.form_field()
            field.initial = saved.get(attribute.pk, "")
            field.widget.attrs["class"] = INPUT
            self.fields[f"{ATTR_PREFIX}{attribute.pk}"] = field

    def attribute_fields(self):
        return [self[f"{ATTR_PREFIX}{a.pk}"] for a in self.attributes]

    def main_fields(self):
        return [f for f in self if not f.name.startswith(ATTR_PREFIX)]

    def save_attribute_values(self, product):
        for attribute in self.attributes:
            value = self.cleaned_data.get(f"{ATTR_PREFIX}{attribute.pk}")
            text = "" if value is None else str(value).strip()
            if text:
                ProductAttributeValue.objects.update_or_create(
                    product=product, attribute=attribute, defaults={"value": text}
                )
            else:
                ProductAttributeValue.objects.filter(product=product, attribute=attribute).delete()


class VariantForm(StyledFormMixin, forms.ModelForm):
    """A variant row. Staff without change_price set prices on new variants only."""

    add_stock = forms.IntegerField(
        min_value=1, required=False, label="Add stock", help_text="Pieces received now."
    )
    user = None

    class Meta:
        model = Variant
        fields = [
            "sku",
            "name",
            "price",
            "compare_at_price",
            "min_order_qty",
            "order_step",
            "weight_grams",
            "track_stock",
            "low_stock_threshold",
            "is_active",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and not self.user.has_perm(PRICE_PERM):
            for name in ("price", "compare_at_price"):
                self.fields[name].disabled = True
        if not self.user.has_perm("inventory.add_stockmovement"):
            del self.fields["add_stock"]


def variant_formset(user, extra=1):
    form = type("VariantFormForUser", (VariantForm,), {"user": user})
    return inlineformset_factory(
        Product,
        Variant,
        form=form,
        extra=extra,
        min_num=1,
        validate_min=True,
        can_delete=False,
    )


class VariantDetailForm(VariantForm):
    """The variant page: same fields, without the stock box (it has its own form)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop("add_stock", None)


class TierForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = PriceTier
        fields = ["min_quantity", "unit_price", "wholesale_only"]


TierFormSet = inlineformset_factory(Variant, PriceTier, form=TierForm, extra=2, can_delete=True)


class ImageForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ProductImage
        fields = ["alt_text", "sort_order"]


ImageFormSet = modelformset_factory(ProductImage, form=ImageForm, extra=0, can_delete=True)


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        if isinstance(data, list | tuple):
            return [super(MultipleImageField, self).clean(d, initial) for d in data]
        return [super().clean(data, initial)] if data else []


class UploadImagesForm(forms.Form):
    images = MultipleImageField(
        required=False,
        label="Add photos",
        help_text="You can choose many photos at once. The first photo is the main photo.",
        widget=MultipleFileInput(attrs={"accept": "image/*", "class": "text-sm"}),
    )


# Stock ---------------------------------------------------------------------------------


class StockChangeForm(StyledFormMixin, forms.Form):
    """Receive new stock, or adjust stock by hand. Saved through apps.inventory.services."""

    kind = forms.ChoiceField(
        choices=[
            (StockMovement.RECEIVED, "Receive new stock"),
            (StockMovement.ADJUSTMENT, "Manual adjustment (+ or -)"),
        ]
    )
    quantity = forms.IntegerField(help_text="For an adjustment, a negative number removes stock.")
    lot = forms.ModelChoiceField(queryset=Lot.objects.all(), required=False)
    cost_per_unit = forms.DecimalField(
        required=False, max_digits=12, decimal_places=0, min_value=0, label="Cost per piece (Rs)"
    )
    note = forms.CharField(required=False, max_length=255)

    def __init__(self, *args, user, variant, **kwargs):
        self.user, self.variant = user, variant
        super().__init__(*args, **kwargs)
        if not user.has_perm(COST_PERM):
            del self.fields["cost_per_unit"]

    def clean(self):
        data = super().clean()
        kind, qty = data.get("kind"), data.get("quantity")
        if qty is None:
            return data
        if kind == StockMovement.RECEIVED and qty <= 0:
            self.add_error("quantity", "Received quantity must be more than 0.")
        if kind == StockMovement.ADJUSTMENT:
            if not self.user.has_perm("inventory.adjust_stock"):
                self.add_error("kind", "You do not have permission to adjust stock.")
            elif qty == 0:
                self.add_error("quantity", "The change cannot be 0.")
            elif not data.get("note"):
                self.add_error("note", "Write a reason for the adjustment.")
            elif qty < 0 and -qty > self.variant.stock_on_hand:
                self.add_error(
                    "quantity",
                    f"Only {self.variant.stock_on_hand} on hand. You cannot remove {-qty}.",
                )
        return data


class ImportForm(StyledFormMixin, forms.Form):
    file = forms.FileField(label="CSV file")
    dry_run = forms.BooleanField(label="Check only (do not save)", required=False, initial=True)


# Orders --------------------------------------------------------------------------------


class TransitionForm(StyledFormMixin, forms.Form):
    note = forms.CharField(required=False, max_length=200)
    courier = forms.CharField(required=False, max_length=60)
    tracking_number = forms.CharField(required=False, max_length=80)


class OrderEditForm(StyledFormMixin, forms.ModelForm):
    """Staff fix the address after the phone call. After dispatch only notes change."""

    class Meta:
        model = Order
        fields = ["full_name", "phone", "email", "city", "address", "landmark", "staff_notes"]
        widgets = {"address": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, address_locked=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["city"].queryset = City.objects.filter(is_active=True)
        if address_locked:
            for name in self.fields:
                if name != "staff_notes":
                    self.fields[name].disabled = True

    def clean_phone(self):
        return normalize_pk_mobile(self.cleaned_data["phone"])

    def save(self, commit=True):
        order = super().save(commit=False)
        order.city_name = order.city.name
        if commit:
            order.save()
        return order


# Owner ---------------------------------------------------------------------------------

STAFF_APPS = ["catalog", "inventory", "orders", "shipping", "accounts", "core"]


class StaffForm(StyledFormMixin, forms.ModelForm):
    """Create or edit a staff account: roles (groups) plus single extra permissions."""

    password = forms.CharField(
        widget=forms.PasswordInput(render_value=False),
        required=False,
        help_text="At least 8 characters. Leave empty to keep the current password.",
    )
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.order_by("name"),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Roles",
    )
    user_permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.filter(content_type__app_label__in=STAFF_APPS)
        .select_related("content_type")
        .order_by("content_type__app_label", "content_type__model", "codename"),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Extra permissions",
    )

    class Meta:
        model = get_user_model()
        fields = ["username", "first_name", "last_name", "email", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields["password"].required = True
            self.fields["password"].help_text = "At least 8 characters."
        else:
            self.fields["groups"].initial = self.instance.groups.all()
            self.fields["user_permissions"].initial = self.instance.user_permissions.all()

    def clean_password(self):
        password = self.cleaned_data.get("password")
        if password:
            password_validation.validate_password(password, self.instance)
        return password

    def clean_is_active(self):
        active = self.cleaned_data["is_active"]
        if not active and self.instance.is_superuser:
            raise ValidationError("You cannot turn off the owner account here.")
        return active

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_staff = True
        if self.cleaned_data.get("password"):
            user.set_password(self.cleaned_data["password"])
        user.save()
        user.groups.set(self.cleaned_data["groups"])
        user.user_permissions.set(self.cleaned_data["user_permissions"])
        return user

    def permission_groups(self):
        """The extra permission checkboxes, grouped by model, for the template."""
        groups, labels = {}, {}
        for choice in self["user_permissions"]:
            perm = choice.data["value"].instance
            model = perm.content_type.model_class()
            key = perm.content_type_id
            labels[key] = model._meta.verbose_name_plural.capitalize() if model else key
            groups.setdefault(key, []).append(choice)
        return [(labels[k], v) for k, v in groups.items()]
