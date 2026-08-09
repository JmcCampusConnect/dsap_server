from rest_framework import permissions


class IsStudentManagementAdmin(permissions.BasePermission):
    """
    Allows access to student management for roles that already have the
    Students menu in the current RBAC matrix.
    """

    allowed_roles = {'SYSTEM_ADMIN', 'SERVICE_DEPT_ADMIN'}

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        role = getattr(getattr(user, 'role_id', None), 'name', None)
        return role in self.allowed_roles
