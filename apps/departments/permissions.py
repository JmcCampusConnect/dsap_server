from rest_framework.permissions import BasePermission


class IsServiceDepartmentAdmin(BasePermission):
    """
    Allows access only to users with the SERVICE_DEPT_ADMIN role.
    """

    message = "Only Service Department Admins can perform this action."

    def has_permission(self, request, view):
        # User must be authenticated
        if not request.user or not request.user.is_authenticated:
            return False

        # User must have a role
        if not hasattr(request.user, "role_id") or request.user.role_id is None:
            return False

        # Role must be SERVICE_DEPT_ADMIN
        return request.user.role_id.name == "SERVICE_DEPT_ADMIN"