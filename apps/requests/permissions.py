from rest_framework import permissions


class IsStudent(permissions.BasePermission):
    """
    Allows access only to authenticated users who have the STUDENT role
    and a linked Student profile.
    """

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return False

        role_name = getattr(getattr(user, 'role_id', None), 'name', None)
        if role_name != 'STUDENT':
            return False

        return hasattr(user, 'student') and user.student is not None
