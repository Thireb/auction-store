from django.db import models
from simple_history.models import HistoricalRecords

from apps.catalog.models import MONEY


class ShippingSettings(models.Model):
    """Store-wide delivery, COD and advance payment settings. There is only 1 row."""

    default_delivery_fee = models.DecimalField(default=250, **MONEY)
    default_cod_fee = models.DecimalField(
        default=0, help_text="Extra charge for Cash on Delivery.", **MONEY
    )
    free_delivery_above = models.DecimalField(
        null=True, blank=True, help_text="No delivery fee at or above this subtotal.", **MONEY
    )
    bulky_item_fee = models.DecimalField(
        default=0,
        help_text="Extra delivery fee once per order that has a bulky item (furniture).",
        **MONEY,
    )
    advance_above_total = models.DecimalField(
        null=True,
        blank=True,
        help_text="Ask for an advance on every order at or above this total.",
        **MONEY,
    )
    advance_percent_above_total = models.PositiveIntegerField(
        default=0, help_text="Advance percent for orders above the total."
    )
    advance_payment_details = models.TextField(
        blank=True,
        help_text="Bank, Easypaisa or JazzCash details for customers who pay an advance.",
    )
    low_stock_default = models.PositiveIntegerField(
        "near empty at (store default)",
        default=2,
        help_text="Staff get an alert when an item has this many pieces or fewer left. "
        "A variant can set its own number.",
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = "shipping and payment settings"
        verbose_name_plural = "shipping and payment settings"

    def __str__(self):
        return "Shipping and payment settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        return cls.objects.get_or_create(pk=1)[0]


class City(models.Model):
    PROVINCES = [
        ("punjab", "Punjab"),
        ("sindh", "Sindh"),
        ("kp", "Khyber Pakhtunkhwa"),
        ("balochistan", "Balochistan"),
        ("ict", "Islamabad Capital Territory"),
        ("gb", "Gilgit-Baltistan"),
        ("ajk", "Azad Jammu and Kashmir"),
    ]

    name = models.CharField(max_length=80, unique=True)
    province = models.CharField(max_length=20, choices=PROVINCES, blank=True)
    is_active = models.BooleanField(default=True, help_text="Untick to stop delivery to this city.")
    cod_allowed = models.BooleanField(default=True)
    delivery_fee = models.DecimalField(
        null=True, blank=True, help_text="Empty uses the default delivery fee.", **MONEY
    )
    cod_fee = models.DecimalField(
        null=True, blank=True, help_text="Empty uses the default COD fee.", **MONEY
    )
    estimated_days = models.CharField(max_length=20, blank=True, help_text='For example "2-4".')
    sort_order = models.PositiveIntegerField(default=0)
    history = HistoricalRecords()

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "cities"

    def __str__(self):
        return self.name
