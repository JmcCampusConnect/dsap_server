from rest_framework import permissions
from.role_constants import Roles

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
        
class IsTeachingStaff(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and
            request.user.is_active and
            request.user.has_role(Roles.SUBJECT_TEACHING_STAFF)
        )
class IsOwnServiceDepartment(permissions.BasePermission):
    """ List: allow dept roles. Object: same service_department_id or SYSTEM_ADMINN bypass """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_active or not request.user.is_authenticated:
            return False
        return request.user.has_any_role([
            Roles.SYSTEM_ADMIN,
            Roles.SERVICE_DEPT_ADMIN,
            Roles.SERVICE_DEPT_STAFF
        ])

    def has_object_permission(self, request, view, obj):
        if request.user.is_system_admin():
            return True
        user_dept = _get_dept_id(request.user, 'service_department_id')  
        obj_dept = _get_dept_id(obj, 'service_department_id')
        if not user_dept or not obj_dept:
            return False
        return user_dept == obj_dept

class IsOwnAcademicDepartment(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_active or not request.user.is_authenticated:
            return False
        return request.user.has_any_role([
            Roles.SUBJECT_TEACHING_STAFF,
            Roles.SYSTEM_ADMIN,
        ])

    def has_object_permission(self, request, view, obj):
        if request.user.is_system_admin():
            return True
        user_dept = _get_dept_id(request.user, 'academic_department_id')
        obj_dept = _get_dept_id(obj, 'academic_department_id')
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