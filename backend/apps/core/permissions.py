from django.contrib.auth.models import Group
from rest_framework.permissions import BasePermission


class IsSuperAdmin(BasePermission):
    """Allows access only to super administrators."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)


class IsPropertyManager(BasePermission):
    """Allows access only to users in the Property Manager group."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.user.is_superuser:
            return True
        return request.user.groups.filter(name="Property Manager").exists()


class IsStaff(BasePermission):
    """Allows access to any staff user."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return bool(request.user.is_staff)


class IsStaffOrSuperAdmin(BasePermission):
    """Allows access to staff users and super administrators."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return bool(request.user.is_staff or request.user.is_superuser)


class HasGroupPermission(BasePermission):
    """
    Allows access based on group membership.
    Usage:
        class SomeView(APIView):
            permission_classes = [HasGroupPermission]
            required_groups = ["Property Manager"]
    """

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.user.is_superuser:
            return True
        required_groups = getattr(view, "required_groups", [])
        if not required_groups:
            return True
        user_groups = request.user.groups.values_list("name", flat=True)
        return bool(set(required_groups) & set(user_groups))


# --- Named, per-capability permission classes -------------------------------
#
# Thin subclasses of the two checks above (IsPropertyManager / IsSuperAdmin) —
# no new authorization logic. Their purpose is purely so each viewset's
# `permission_classes` states what it actually requires ("can this user
# record a payment?") instead of a generic role name repeated at every call
# site. See docs/ARCHITECTURE_DECISIONS.md for the RBAC model these map to.

class CanManageProperty(IsPropertyManager):
    """Create/update/archive properties, sections, units, and pricing rules."""


class CanManageOccupants(IsPropertyManager):
    """Create/update/archive occupant records."""


class CanManageOccupancy(IsPropertyManager):
    """Assign/checkout occupancy records."""


class CanRecordPayment(IsPropertyManager):
    """Record payments."""


class CanManageUsers(IsSuperAdmin):
    """Create/update/deactivate user accounts and manage group membership.

    Deliberately IsSuperAdmin, not IsPropertyManager: a Property Manager must
    never be able to reach user-account management, since resetting another
    account's password (a Property Manager CAN do everything else a
    superuser-gated action would need) is an effective privilege-escalation
    path if this is under-scoped.
    """


class CanViewAuditLog(IsSuperAdmin):
    """View the audit trail."""


class CanManageBackups(IsSuperAdmin):
    """Create/restore backups and export data."""
