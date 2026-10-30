from django.contrib import admin, messages
from simple_history.admin import SimpleHistoryAdmin

from .models import WholesaleProfile

APPROVE_PERM = "accounts.approve_wholesale_buyer"


@admin.register(WholesaleProfile)
class WholesaleProfileAdmin(SimpleHistoryAdmin):
    list_display = ["business_name", "user", "city", "status", "created_at", "reviewed_by"]
    list_filter = ["status", "created_at"]
    search_fields = ["business_name", "user__username", "user__first_name", "city"]
    readonly_fields = ["user", "status", "reviewed_by", "created_at"]
    actions = ["approve", "reject"]

    def has_add_permission(self, request):
        return False

    def _review(self, request, queryset, status):
        if not request.user.has_perm(APPROVE_PERM):
            self.message_user(request, "You cannot approve wholesale buyers.", messages.ERROR)
            return
        count = queryset.update(status=status, reviewed_by=request.user)
        self.message_user(request, f"{count} buyers marked {status}.")

    @admin.action(description="Approve selected wholesale buyers")
    def approve(self, request, queryset):
        self._review(request, queryset, WholesaleProfile.APPROVED)

    @admin.action(description="Reject selected wholesale buyers")
    def reject(self, request, queryset):
        self._review(request, queryset, WholesaleProfile.REJECTED)
