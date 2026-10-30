import uuid

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from simple_history.models import HistoricalRecords

from apps.catalog.models import MONEY, Variant
from apps.core.phone import display_pk_mobile
from apps.shipping.models import City


class Order(models.Model):
    PENDING = "pending_confirmation"
    AWAITING_ADVANCE = "awaiting_advance"
    CONFIRMED = "confirmed"
    PACKED = "packed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    RETURNED = "returned"
    STATUS_CHOICES = [
        (PENDING, "Pending confirmation"),
        (AWAITING_ADVANCE, "Awaiting advance"),
        (CONFIRMED, "Confirmed"),
        (PACKED, "Packed"),
        (SHIPPED, "Shipped"),
        (DELIVERED, "Delivered"),
        (COMPLETED, "Completed (cash received)"),
        (CANCELLED, "Cancelled"),
        (RETURNED, "Returned / refused"),
    ]
    OPEN_STATUSES = [PENDING, AWAITING_ADVANCE, CONFIRMED, PACKED, SHIPPED]

    ADVANCE_NOT_REQUIRED, ADVANCE_PENDING, ADVANCE_RECEIVED = "not_required", "pending", "received"
    ADVANCE_STATUS_CHOICES = [
        (ADVANCE_NOT_REQUIRED, "Not required"),
        (ADVANCE_PENDING, "Pending"),
        (ADVANCE_RECEIVED, "Received"),
    ]

    number = models.CharField(max_length=20, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name="orders",
        on_delete=models.SET_NULL,
    )
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default=PENDING)

    # Customer and address, copied at checkout.
    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=16, db_index=True)
    email = models.EmailField(blank=True)
    city = models.ForeignKey(City, related_name="orders", on_delete=models.PROTECT)
    city_name = models.CharField(max_length=80)
    address = models.TextField()
    landmark = models.CharField(max_length=200, blank=True)
    customer_notes = models.TextField(blank=True)

    # Money, calculated on the server at checkout.
    subtotal = models.DecimalField(**MONEY)
    delivery_fee = models.DecimalField(**MONEY)
    cod_fee = models.DecimalField(**MONEY)
    total = models.DecimalField(**MONEY)
    advance_amount = models.DecimalField(default=0, **MONEY)
    advance_status = models.CharField(
        max_length=12, choices=ADVANCE_STATUS_CHOICES, default=ADVANCE_NOT_REQUIRED
    )
    advance_proof = models.ImageField(upload_to="advance-proofs/%Y/%m/", blank=True)

    staff_notes = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "-created_at"])]
        permissions = [("cancel_confirmed_order", "Can cancel an order after confirmation")]

    def __str__(self):
        return self.number

    def save(self, *args, **kwargs):
        if self.number:
            return super().save(*args, **kwargs)
        # The number comes from the primary key, so 2 orders at the same time never clash.
        self.number = f"tmp-{uuid.uuid4().hex[:16]}"
        super().save(*args, **kwargs)
        self.number = f"AS-{timezone.localdate():%y%m}-{self.pk:05d}"
        Order.objects.filter(pk=self.pk).update(number=self.number)

    @property
    def phone_display(self):
        return display_pk_mobile(self.phone)

    @property
    def balance_after_advance(self):
        return self.total - self.advance_amount

    @property
    def cod_amount(self):
        """Cash the courier collects."""
        if self.advance_status == self.ADVANCE_RECEIVED:
            return self.total - self.advance_amount
        return self.total

    def get_thanks_url(self):
        return reverse("orders:thanks", args=[self.number])


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    variant = models.ForeignKey(
        Variant, null=True, blank=True, related_name="order_items", on_delete=models.SET_NULL
    )
    product_title = models.CharField(max_length=200)
    variant_name = models.CharField(max_length=120, blank=True)
    sku = models.CharField(max_length=64)
    unit_price = models.DecimalField(**MONEY)
    regular_price = models.DecimalField(**MONEY)
    quantity = models.PositiveIntegerField()
    line_total = models.DecimalField(**MONEY)
    advance_amount = models.DecimalField(default=0, **MONEY)

    class Meta:
        ordering = ["pk"]

    def __str__(self):
        return f"{self.quantity} x {self.product_title}"
