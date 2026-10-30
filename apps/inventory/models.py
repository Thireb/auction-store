from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from apps.catalog.models import MONEY, Variant


class Lot(models.Model):
    """One purchase from an auction or an exporter."""

    reference = models.CharField(max_length=60, unique=True, help_text='For example "DXB-2026-07".')
    source = models.CharField(max_length=120, blank=True, help_text="Auction house or exporter.")
    purchase_date = models.DateField(null=True, blank=True)
    total_cost = models.DecimalField(
        null=True, blank=True, help_text="Price paid for the lot.", **MONEY
    )
    landed_cost = models.DecimalField(
        null=True, blank=True, help_text="Shipping, customs and other costs.", **MONEY
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["-purchase_date", "-created_at"]
        permissions = [("view_cost_and_profit", "Can see costs and profit")]

    def __str__(self):
        return self.reference


class StockItem(models.Model):
    """The stock of one variant that came from one lot. Used for cost and for FIFO dispatch."""

    variant = models.ForeignKey(Variant, related_name="stock_items", on_delete=models.PROTECT)
    lot = models.ForeignKey(
        Lot, null=True, blank=True, related_name="stock_items", on_delete=models.PROTECT
    )
    quantity_received = models.PositiveIntegerField(default=0)
    quantity_on_hand = models.PositiveIntegerField(default=0)
    cost_per_unit = models.DecimalField(null=True, blank=True, **MONEY)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["received_at", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["variant", "lot"], name="unique_variant_lot"),
        ]

    def __str__(self):
        return f"{self.variant} ({self.lot or 'no lot'}): {self.quantity_on_hand}"


class StockMovement(models.Model):
    """One change of stock. Rows are never edited or deleted: they are the audit trail."""

    RECEIVED = "received"
    RESERVED = "reserved"
    RELEASED = "released"
    DISPATCHED = "dispatched"
    RETURNED = "returned"
    ADJUSTMENT = "adjustment"
    KIND_CHOICES = [
        (RECEIVED, "Received into stock"),
        (RESERVED, "Reserved for an order"),
        (RELEASED, "Reservation released"),
        (DISPATCHED, "Dispatched to the customer"),
        (RETURNED, "Returned to stock"),
        (ADJUSTMENT, "Manual adjustment"),
    ]

    variant = models.ForeignKey(Variant, related_name="stock_movements", on_delete=models.PROTECT)
    lot = models.ForeignKey(
        Lot, null=True, blank=True, related_name="movements", on_delete=models.PROTECT
    )
    kind = models.CharField(max_length=12, choices=KIND_CHOICES)
    quantity = models.IntegerField(help_text="Positive adds, negative removes.")
    on_hand_after = models.IntegerField()
    reserved_after = models.IntegerField()
    reference = models.CharField(max_length=60, blank=True, help_text="Order number or note.")
    note = models.CharField(max_length=255, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        permissions = [("adjust_stock", "Can adjust stock by hand")]
        indexes = [models.Index(fields=["variant", "-created_at"])]

    def __str__(self):
        return f"{self.get_kind_display()} {self.quantity:+d} {self.variant}"
