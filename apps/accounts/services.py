from django.core.exceptions import PermissionDenied

from .models import WholesaleProfile

APPROVE_PERM = "accounts.approve_wholesale_buyer"


def review_wholesale(profile, status, *, user):
    """Approve or reject a wholesale request. Needs the approve_wholesale_buyer permission."""
    if not user.has_perm(APPROVE_PERM):
        raise PermissionDenied("You cannot approve wholesale buyers.")
    if status not in (WholesaleProfile.APPROVED, WholesaleProfile.REJECTED):
        raise ValueError(f"Unknown status {status!r}.")
    profile.status = status
    profile.reviewed_by = user
    profile.save(update_fields=["status", "reviewed_by"])
    return profile
