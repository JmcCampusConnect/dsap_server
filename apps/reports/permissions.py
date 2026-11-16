"""
Reports — Permissions
Enforces role-based access control (RBAC) for reporting modules.
Allowed roles: SYSTEM_ADMIN, SERVICE_DEPT_ADMIN, SERVICE_DEPT_STAFF.
Students and unauthorized roles receive 403 Forbidden.
"""
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied

from apps.accounts.role_constants import Roles

ALLOWED_REPORT_ROLES = [
    Roles.SYSTEM_ADMIN,
    Roles.SERVICE_DEPT_ADMIN,
    Roles.SERVICE_DEPT_STAFF,
]

ALLOWED_REVENUE_REPORT_ROLES = [
    Roles.SYSTEM_ADMIN,
    Roles.SERVICE_DEPT_ADMIN,
]


class IsReportViewer(permissions.BasePermission):
    """
    Grants access only to authenticated users with SYSTEM_ADMIN,
    SERVICE_DEPT_ADMIN, or SERVICE_DEPT_STAFF roles.
    """

    message = "You do not have permission to access these reports."

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated or not getattr(user, 'is_active', False):
            return False

        if not user.has_any_role(ALLOWED_REPORT_ROLES):
            raise PermissionDenied({
                "error": {
                    "code": "PERMISSION_DENIED",
                    "message": self.message
                }
            })

        # Non-system admins must have an assigned service department
        if not user.is_system_admin() and not getattr(user, 'service_department_id', None):
            raise PermissionDenied({
                "error": {
                    "code": "PERMISSION_DENIED",
                    "message": "User is not assigned to any service department."
                }
            })

        return True


class CanViewRevenueReport(permissions.BasePermission):
    """
    Restricts revenue reports to SYSTEM_ADMIN and SERVICE_DEPT_ADMIN.
    SERVICE_DEPT_STAFF is denied access to financial/revenue reporting.
    """

    message = "You do not have permission to access revenue reports."

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated or not getattr(user, 'is_active', False):
            return False

        if not user.has_any_role(ALLOWED_REVENUE_REPORT_ROLES):
            raise PermissionDenied({
                "error": {
                    "code": "PERMISSION_DENIED",
                    "message": self.message
                }
            })

        if not user.is_system_admin() and not getattr(user, 'service_department_id', None):
            raise PermissionDenied({
                "error": {
                    "code": "PERMISSION_DENIED",
                    "message": "User is not assigned to any service department."
                }
            })

        return True
