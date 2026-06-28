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
