from rest_framework import permissions
from .role_constants import Roles

def _get_dept_id(obj, field_name: str):
    """ Safely get department id from FK object or raw id. """
    val = getattr(obj, field_name, None)
    if val is None:
        return None
    return getattr(val, 'id', val)
class IsSystemAdmin(permissions.BasePermission):
    """ Allows access only to SYSTEM_ADMIN users """
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.is_active and
            request.user.has_role(Roles.SYSTEM_ADMIN)
        )

class IsServiceDeptAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.is_active and
            request.user.has_role(Roles.SERVICE_DEPT_ADMIN)
        )
        
class IsServiceDeptStaff(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.is_active and
            request.user.has_role(Roles.SERVICE_DEPT_STAFF)
        )

class IsStudent(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and
            request.user.is_active and
            request.user.has_role(Roles.STUDENT)
        )
        
class IsUserManager(permissions.BasePermission):
    """
    Gate for user-mutating actions.

    SYSTEM_ADMIN  -> full management.
    SERVICE_DEPT_ADMIN -> management within own service department
    (object-level check enforced separately by IsOwnServiceDepartment).
    SERVICE_DEPT_STAFF -> read-only; rejected here with 403.
    """

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_active
            and request.user.has_any_role(
                [Roles.SYSTEM_ADMIN, Roles.SERVICE_DEPT_ADMIN]
            )
        )
class IsOwnServiceDepartment(permissions.BasePermission):
    """
    Role gate + object-level service department ownership.

    Role gate (has_permission): allowed for SYSTEM_ADMIN, SERVICE_DEPT_ADMIN
    and SERVICE_DEPT_STAFF (staff are read-only and are filtered by
    IsUserManager on mutations).

    Object gate: SYSTEM_ADMIN bypasses; every other role must share the
    same service department as the target object, OR the target is the
    requesting user themselves.
    """
    
    ALLOWED_ROLES = (
        Roles.SYSTEM_ADMIN,
        Roles.SERVICE_DEPT_ADMIN,
        Roles.SERVICE_DEPT_STAFF,
    )
    def has_permission(self, request, view):
        if not request.user or not request.user.is_active or not request.user.is_authenticated:
            return False
        return request.user.has_any_role(list(self.ALLOWED_ROLES))

    def has_object_permission(self, request, view, obj):
        if request.user.is_system_admin():
            return True
        
        if getattr(obj, 'id', None) == request.user.id:
            return True
        
        user_dept = _get_dept_id(request.user, 'service_department_id')  
        obj_dept = _get_dept_id(obj, 'service_department_id')
        if not user_dept or not obj_dept:
            return False
        return user_dept == obj_dept

class IsSelfStudent(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'user'):
            return obj.user.id == request.user.id
        return getattr(obj, 'id', None) == request.user.id
    
class IsSelfOrSystemAdmin(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_system_admin():
            return True
        return IsSelfStudent().has_object_permission(request, view, obj)


class CanVerifyPayment(permissions.BasePermission):
    """Scope payment reads and verification writes to the owning student/department."""

    READ_ROLES = (
        Roles.SYSTEM_ADMIN,
        Roles.SERVICE_DEPT_ADMIN,
        Roles.SERVICE_DEPT_STAFF,
        Roles.STUDENT,
    )
    VERIFY_ROLES = (Roles.SERVICE_DEPT_ADMIN, Roles.SERVICE_DEPT_STAFF)

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated or not user.is_active:
            return False
        allowed_roles = self.READ_ROLES if request.method in permissions.SAFE_METHODS else self.VERIFY_ROLES
        return user.role_name in allowed_roles

    def has_object_permission(self, request, view, payment):
        user = request.user
        request_obj = payment.request_id
        if user.role_name == Roles.SYSTEM_ADMIN:
            return request.method in permissions.SAFE_METHODS
        if user.role_name == Roles.STUDENT:
            return request_obj.student_id.user_id_id == user.id
        if user.role_name in self.VERIFY_ROLES:
            return (
                user.service_department_id_id is not None
                and request_obj.service_id.service_department_id_id
                == user.service_department_id_id
            )
        return False


class CanManageServiceDepartment(permissions.BasePermission):
    """Allow system admins and the owning department admin to edit department details."""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.role_name in (Roles.SYSTEM_ADMIN, Roles.SERVICE_DEPT_ADMIN)
        )

    def has_object_permission(self, request, view, department):
        user = request.user
        if user.role_name == Roles.SYSTEM_ADMIN:
            return True
        return (
            user.service_department_id_id is not None
            and user.service_department_id_id == department.id
        )