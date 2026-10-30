from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords


class WholesaleProfile(models.Model):
    """A buyer's request for wholesale prices. Staff approve or reject it in the admin."""

    PENDING, APPROVED, REJECTED = "pending", "approved", "rejected"
    STATUS_CHOICES = [(PENDING, "Pending"), (APPROVED, "Approved"), (REJECTED, "Rejected")]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, related_name="wholesale_profile", on_delete=models.CASCADE
    )
    business_name = models.CharField(max_length=120)
    city = models.CharField(max_length=80)
    details = models.TextField(blank=True, help_text="What the buyer sells and how much.")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name="+",
        on_delete=models.SET_NULL,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["-created_at"]
        permissions = [("approve_wholesale_buyer", "Can approve wholesale buyers")]

    def __str__(self):
        return f"{self.business_name} ({self.get_status_display()})"

    @property
    def is_approved(self):
        return self.status == self.APPROVED
