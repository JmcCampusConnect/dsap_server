from rest_framework import permissions

class IsSystemAdmin(permissions.BasePermission):
    """ Allows access only to SYSTEM_ADMIN users """
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.role_id and               # use role_id
            request.user.role_id.name == 'SYSTEM_ADMIN'
        )

class IsOwnServiceDepartment(permissions.BasePermission):
    """ Allows access only to users whose service department matches the requested resource """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if not request.user.role_id:               # use role_id
            return False
        user_role = request.user.role_id.name
        return user_role in ['SERVICE_DEPT_ADMIN', 'SERVICE_DEPT_STAFF']

    def has_object_permission(self, request, view, obj):
        user_dept = getattr(request.user, 'service_department_id', None)  # field name
        obj_dept = getattr(obj, 'service_department_id', None)
        if not user_dept or not obj_dept:
            return False
        if hasattr(user_dept, 'id'):
            return user_dept.id == obj_dept.id
        return user_dept == obj_dept

class IsOwnAcademicDepartment(permissions.BasePermission):
    """ Allows access only to users whose academic department matches the requested resource """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if not request.user.role_id:               # use role_id
            return False
        user_role = request.user.role_id.name
        return user_role in ['SUBJECT_TEACHING_STAFF']

    def has_object_permission(self, request, view, obj):
        user_dept = getattr(request.user, 'academic_department_id', None)
        obj_dept = getattr(obj, 'academic_department_id', None)
        if not user_dept or not obj_dept:
            return False
        if hasattr(user_dept, 'id'):
            return user_dept.id == obj_dept.id
        return user_dept == obj_dept

class IsSelfStudent(permissions.BasePermission):
    """ Allows access only to the student's own records """
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.role_id and               # use role_id
            request.user.role_id.name == 'STUDENT'
        )

    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'user'):
            return obj.user.id == request.user.id
        return obj.id == request.user.id