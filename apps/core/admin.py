from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Page


@admin.register(Page)
class PageAdmin(SimpleHistoryAdmin):
    list_display = ["title", "slug", "show_in_footer", "is_active", "sort_order"]
    list_editable = ["show_in_footer", "is_active", "sort_order"]
    prepopulated_fields = {"slug": ["title"]}
    search_fields = ["title", "body"]
