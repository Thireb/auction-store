from django.conf import settings
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from simple_history.models import HistoricalRecords

from apps.catalog.models import MONEY, Variant, unique_slug


class LotQuerySet(models.QuerySet):
    def public(self):
        return self.filter(is_public=True)

    def open(self, now=None):
        """Lots whose pieces customers can see and buy now."""
        return self.filter(Q(opens_at__isnull=True) | Q(opens_at__lte=now or timezone.now()))

    def upcoming(self, now=None):
        return self.filter(opens_at__gt=now or timezone.now())


class Lot(models.Model):
    """One purchase from an auction or an exporter.

    A public lot also has a page in the store. Its pieces stay hidden until `opens_at`.
    """

    reference = models.CharField(max_length=60, unique=True, help_text='For example "DXB-2026-07".')
    slug = models.SlugField(max_length=80, unique=True, blank=True)
    source = models.CharField(max_length=120, blank=True, help_text="Auction house or exporter.")
    purchase_date = models.DateField(null=True, blank=True)
    total_cost = models.DecimalField(
        null=True, blank=True, help_text="Price paid for the lot.", **MONEY
    )
    landed_cost = models.DecimalField(
        null=True, blank=True, help_text="Shipping, customs and other costs.", **MONEY
    )
    notes = models.TextField(blank=True)
    is_public = models.BooleanField(
        "show in the store",
        default=False,
        help_text="Give this lot its own page in the store, with its story and pieces.",
    )
    public_title = models.CharField(
        max_length=120,
        blank=True,
        help_text='What customers read, for example "Dubai hotel refit auction".',
    )
    story = models.TextField(
        blank=True, help_text="A few lines about where the pieces come from. Plain text."
    )
    cover_image = models.ImageField(upload_to="lots/", blank=True)
    opens_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Pieces stay hidden until this time, and the store shows a countdown. "
        "Empty opens the lot now.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    objects = LotQuerySet.as_manager()

    class Meta:
        ordering = ["-purchase_date", "-created_at"]
        permissions = [("view_cost_and_profit", "Can see costs and profit")]

    def __str__(self):
        return self.reference

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.reference, max_length=80)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("lots:detail", args=[self.slug])

    @property
    def title(self):
        return self.public_title or self.source or self.reference

    @property
    def is_open(self):
        return self.opens_at is None or self.opens_at <= timezone.now()


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


class LotPhotoQuerySet(models.QuerySet):
    def in_tray(self, lot):
        """Photos of one lot's tray. `lot=None` is the "No lot" tray."""
        return self.filter(lot=lot) if lot else self.filter(lot__isnull=True)

    def pickable(self):
        """Photos staff can still put on an item: unassigned, or marked "use again"."""
        return self.filter(
            Q(status=LotPhoto.UNASSIGNED) | Q(status=LotPhoto.ASSIGNED, reusable=True)
        )


class LotPhoto(models.Model):
    """A photo in a lot's tray. Staff upload many at once, then put them on items.

    Putting a photo on an item makes a ProductImage that uses the same file. A photo
    can go on a second item only after a "use again".
    """

    UNASSIGNED, ASSIGNED, NOT_USABLE = "unassigned", "assigned", "not_usable"
    STATUS_CHOICES = [
        (UNASSIGNED, "Unassigned"),
        (ASSIGNED, "Assigned"),
        (NOT_USABLE, "Not usable"),
    ]

    lot = models.ForeignKey(
        Lot, null=True, blank=True, related_name="photos", on_delete=models.PROTECT
    )
    image = models.ImageField(upload_to="tray/%Y/%m/")
    thumbnail = models.ImageField(upload_to="tray/thumbs/%Y/%m/", blank=True)
    original_name = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=UNASSIGNED)
    reusable = models.BooleanField(
        default=False, help_text='Set by "Use again": the photo shows in the picker once more.'
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name="+",
        on_delete=models.SET_NULL,
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name="+",
        on_delete=models.SET_NULL,
    )
    assigned_at = models.DateTimeField(null=True, blank=True)
    history = HistoricalRecords()

    objects = LotPhotoQuerySet.as_manager()

    class Meta:
        ordering = ["uploaded_at", "pk"]
        indexes = [models.Index(fields=["lot", "status"])]

    def __str__(self):
        return self.original_name or self.image.name

    @property
    def thumb_url(self):
        return (self.thumbnail or self.image).url
