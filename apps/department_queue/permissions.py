"""
Department Queue — Permissions
Enforces role and department-scoping rules for all queue management actions.
"""
from rest_framework import permissions
from apps.accounts.role_constants import Roles


DEPT_STAFF_ROLES = [Roles.SERVICE_DEPT_ADMIN, Roles.SERVICE_DEPT_STAFF, Roles.SYSTEM_ADMIN]


class IsDeptQueueUser(permissions.BasePermission):
    """
    Allows only SERVICE_DEPT_ADMIN, SERVICE_DEPT_STAFF, and SYSTEM_ADMIN.
    """

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        return bool(
            user
            and user.is_authenticated
            and getattr(user, 'is_active', False)
            and user.has_any_role(DEPT_STAFF_ROLES)
        )


class IsDeptAdmin(permissions.BasePermission):
    """Restricts to SERVICE_DEPT_ADMIN and SYSTEM_ADMIN only."""

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        return bool(
            user
            and user.is_authenticated
            and getattr(user, 'is_active', False)
            and user.has_any_role([Roles.SERVICE_DEPT_ADMIN, Roles.SYSTEM_ADMIN])
        )
