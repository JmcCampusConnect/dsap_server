from rest_framework.permissions import BasePermission


class IsSystemAdmin(BasePermission):
    """Allow only users whose role is SYSTEM_ADMIN."""

    message = "Only System Admins can perform this action."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if not hasattr(request.user, "role_id") or request.user.role_id is None:
            return False
        return request.user.role_id.name == "SYSTEM_ADMIN"


class IsServiceDeptAdmin(BasePermission):
    """Allow only users whose role is SERVICE_DEPT_ADMIN."""

    message = "Only Service Department Admins can perform this action."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if not hasattr(request.user, "role_id") or request.user.role_id is None:
            return False
        return request.user.role_id.name == "SERVICE_DEPT_ADMIN"

    def has_object_permission(self, request, view, obj):
        """Service Dept Admin can only manage services in their own department."""
        return obj.service_department_id.hod_user_id == request.user
