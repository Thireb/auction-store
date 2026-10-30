from datetime import timedelta
from decimal import Decimal

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from simple_history.models import HistoricalRecords

MONEY = {"max_digits": 12, "decimal_places": 0, "validators": [MinValueValidator(Decimal("0"))]}


def unique_slug(instance, value, max_length=200):
    """Make a slug from `value` that is unique for the model of `instance`."""
    base = slugify(value)[: max_length - 10] or "item"
    slug, n = base, 2
    qs = type(instance)._default_manager.exclude(pk=instance.pk)
    while qs.filter(slug=slug).exists():
        slug, n = f"{base}-{n}", n + 1
    return slug


class SluggedModel(models.Model):
    slug = models.SlugField(max_length=200, unique=True, blank=True)

    class Meta:
        abstract = True

    def slug_source(self):
        raise NotImplementedError

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.slug_source())
        super().save(*args, **kwargs)


class Category(SluggedModel):
    name = models.CharField(max_length=120)
    parent = models.ForeignKey(
        "self", null=True, blank=True, related_name="children", on_delete=models.PROTECT
    )
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="categories/", blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return " > ".join(c.name for c in self.ancestors(include_self=True))

    def slug_source(self):
        return self.name

    def get_absolute_url(self):
        return reverse("catalog:category", args=[self.slug])

    def clean(self):
        node = self.parent
        while node is not None:
            if node.pk == self.pk:
                raise ValidationError({"parent": "A category cannot be inside itself."})
            node = node.parent

    def ancestors(self, include_self=False):
        """Return the categories from the root down to this one."""
        chain, node = [], self if include_self else self.parent
        while node is not None:
            chain.append(node)
            node = node.parent
        return list(reversed(chain))

    def descendant_ids(self, include_self=True):
        ids = [self.pk] if include_self else []
        frontier = [self.pk]
        while frontier:
            frontier = list(
                Category.objects.filter(parent_id__in=frontier).values_list("pk", flat=True)
            )
            ids.extend(frontier)
        return ids

    def all_attributes(self):
        """Attributes of this category and of all its parents."""
        ids = [c.pk for c in self.ancestors(include_self=True)]
        return (
            Attribute.objects.filter(categories__in=ids).distinct().order_by("sort_order", "name")
        )


class Attribute(SluggedModel):
    """A product property that the owner defines in the admin, for example "Strap type"."""

    TEXT, NUMBER, CHOICE, YES_NO = "text", "number", "choice", "yes_no"
    TYPE_CHOICES = [(TEXT, "Text"), (NUMBER, "Number"), (CHOICE, "Choice"), (YES_NO, "Yes / No")]

    name = models.CharField(max_length=80)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=TEXT)
    choices = models.TextField(
        blank=True, help_text="For the Choice type only. One option on each line."
    )
    unit = models.CharField(max_length=20, blank=True, help_text='For example "mm" or "ml".')
    categories = models.ManyToManyField(
        Category,
        related_name="attributes",
        blank=True,
        help_text="Products in these categories and their sub-categories get this attribute.",
    )
    is_filterable = models.BooleanField(default=True, help_text="Show as a filter in the store.")
    sort_order = models.PositiveIntegerField(default=0)
    history = HistoricalRecords()

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return f"{self.name} ({self.unit})" if self.unit else self.name

    def slug_source(self):
        return self.name

    @property
    def choice_list(self):
        return [line.strip() for line in self.choices.splitlines() if line.strip()]

    def clean(self):
        if self.type == self.CHOICE and not self.choice_list:
            raise ValidationError({"choices": "Add at least 1 option for a Choice attribute."})

    def form_field(self):
        """A form field for this attribute. The value is always stored as text."""
        label = str(self)
        if self.type == self.NUMBER:
            return forms.DecimalField(label=label, required=False)
        if self.type == self.CHOICE:
            options = [("", "---------")] + [(c, c) for c in self.choice_list]
            return forms.ChoiceField(label=label, choices=options, required=False)
        if self.type == self.YES_NO:
            options = [("", "---------"), ("Yes", "Yes"), ("No", "No")]
            return forms.ChoiceField(label=label, choices=options, required=False)
        return forms.CharField(label=label, max_length=200, required=False)


class Brand(SluggedModel):
    name = models.CharField(max_length=120, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def slug_source(self):
        return self.name


class ProductQuerySet(models.QuerySet):
    def visible(self):
        """Products a customer can open."""
        return self.filter(is_active=True, category__is_active=True)

    def listed(self):
        """Products in lists. Sold-out products stay listed for SOLD_OUT_LISTED_DAYS days."""
        cutoff = timezone.now() - timedelta(days=settings.SOLD_OUT_LISTED_DAYS)
        return self.visible().filter(Q(sold_out_at__isnull=True) | Q(sold_out_at__gte=cutoff))


class Product(SluggedModel):
    CONDITION_CHOICES = [
        ("new", "New"),
        ("open_box", "Open box"),
        ("used_like_new", "Used - like new"),
        ("used_good", "Used - good"),
        ("as_is", "As is / damaged"),
    ]

    title = models.CharField(max_length=200)
    category = models.ForeignKey(Category, related_name="products", on_delete=models.PROTECT)
    brand = models.ForeignKey(
        Brand, null=True, blank=True, related_name="products", on_delete=models.SET_NULL
    )
    description = models.TextField(blank=True)
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default="new")
    origin_note = models.CharField(
        max_length=200, blank=True, help_text='For example "Dubai auction, March 2026".'
    )
    is_active = models.BooleanField(default=True, help_text="Untick to hide from the store.")
    is_featured = models.BooleanField(default=False)
    sold_out_at = models.DateTimeField(
        null=True, blank=True, editable=False, help_text="Set when the last piece is sold."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords(excluded_fields=["sold_out_at"])

    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["is_active", "-created_at"])]

    def __str__(self):
        return self.title

    def slug_source(self):
        return self.title

    def get_absolute_url(self):
        return reverse("catalog:product", args=[self.slug])

    @property
    def main_image(self):
        images = list(self.images.all())
        return images[0] if images else None

    def active_variants(self):
        return [v for v in self.variants.all() if v.is_active]

    @property
    def is_sold_out(self):
        variants = self.active_variants()
        return not any(v.in_stock for v in variants)

    def update_sold_out(self):
        """Set or clear sold_out_at from the current stock. Called after each stock change."""
        sold_out = not any(v.in_stock for v in self.variants.filter(is_active=True))
        if sold_out and self.sold_out_at is None:
            self.sold_out_at = timezone.now()
        elif not sold_out and self.sold_out_at is not None:
            self.sold_out_at = None
        else:
            return
        Product.objects.filter(pk=self.pk).update(sold_out_at=self.sold_out_at)

    @property
    def min_price(self):
        prices = [v.price for v in self.active_variants()]
        return min(prices) if prices else None

    def attribute_values(self):
        """(attribute, value) pairs in attribute order, for the product page."""
        values = self.attribute_values_set.select_related("attribute")
        return sorted(
            ((v.attribute, v.value) for v in values if v.value),
            key=lambda pair: (pair[0].sort_order, pair[0].name),
        )


class Variant(models.Model):
    product = models.ForeignKey(Product, related_name="variants", on_delete=models.CASCADE)
    sku = models.CharField("SKU", max_length=64, unique=True)
    name = models.CharField(
        max_length=120,
        blank=True,
        help_text='Option label, for example "Black / 42". Empty if only 1.',
    )
    price = models.DecimalField(**MONEY)
    compare_at_price = models.DecimalField(
        null=True, blank=True, help_text="Old price, shown crossed out.", **MONEY
    )
    weight_grams = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    # Stock numbers change only through apps.inventory.services, which also writes the history.
    track_stock = models.BooleanField(
        default=True, help_text="Untick for items that are always available."
    )
    stock_on_hand = models.IntegerField(default=0, editable=False)
    stock_reserved = models.IntegerField(default=0, editable=False)
    low_stock_threshold = models.PositiveIntegerField(
        default=2, help_text="Show in the low stock list at or below this quantity."
    )
    min_order_qty = models.PositiveIntegerField(
        "minimum order quantity", default=1, validators=[MinValueValidator(1)]
    )
    order_step = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Sold in multiples of this number, for example 12 for a pack of 12.",
    )
    history = HistoricalRecords(excluded_fields=["stock_on_hand", "stock_reserved"])

    class Meta:
        ordering = ["sort_order", "pk"]
        permissions = [("change_price", "Can change prices of existing variants")]

    def __str__(self):
        return f"{self.product.title} - {self.name}" if self.name else self.product.title

    @property
    def stock_available(self):
        return self.stock_on_hand - self.stock_reserved

    @property
    def in_stock(self):
        return not self.track_stock or self.stock_available > 0


class PriceTier(models.Model):
    """A lower unit price from a minimum quantity. Wholesale-only tiers need an approved buyer."""

    variant = models.ForeignKey(Variant, related_name="price_tiers", on_delete=models.CASCADE)
    min_quantity = models.PositiveIntegerField(validators=[MinValueValidator(2)])
    unit_price = models.DecimalField(**MONEY)
    wholesale_only = models.BooleanField(
        default=False, help_text="Only approved wholesale buyers get this price."
    )
    history = HistoricalRecords()

    class Meta:
        ordering = ["wholesale_only", "min_quantity"]
        constraints = [
            models.UniqueConstraint(
                fields=["variant", "min_quantity", "wholesale_only"], name="unique_price_tier"
            )
        ]

    def __str__(self):
        label = "wholesale " if self.wholesale_only else ""
        return f"{self.min_quantity}+ {label}at Rs {self.unit_price:,}"


class ProductImage(models.Model):
    product = models.ForeignKey(Product, related_name="images", on_delete=models.CASCADE)
    image = models.ImageField(upload_to="products/%Y/%m/")
    alt_text = models.CharField(max_length=200, blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "pk"]

    def __str__(self):
        return self.alt_text or self.image.name


class ProductAttributeValue(models.Model):
    product = models.ForeignKey(
        Product, related_name="attribute_values_set", on_delete=models.CASCADE
    )
    attribute = models.ForeignKey(Attribute, related_name="values", on_delete=models.CASCADE)
    value = models.CharField(max_length=200)
    history = HistoricalRecords()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["product", "attribute"], name="unique_product_attribute"
            )
        ]
        indexes = [models.Index(fields=["attribute", "value"])]

    def __str__(self):
        return f"{self.attribute.name}: {self.value}"
