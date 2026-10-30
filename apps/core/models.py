from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from simple_history.models import HistoricalRecords


class Page(models.Model):
    """A simple content page edited in the admin: About, Contact, Delivery info, FAQ."""

    title = models.CharField(max_length=120)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    body = models.TextField(help_text="Plain text. Empty lines start new paragraphs.")
    show_in_footer = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["sort_order", "title"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("core:page", args=[self.slug])
