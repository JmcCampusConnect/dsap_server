from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.departments.models import ServiceDepartment
from apps.departments.serializers import ServiceDepartmentSerializer
from apps.accounts.permissions import IsSystemAdmin, IsOwnServiceDepartment
from apps.accounts.role_constants import Roles

class ServiceDepartmentViewSet(viewsets.ModelViewSet):
    serializer_class = ServiceDepartmentSerializer
    
    def get_queryset(self):
        user = self.request.user
        qs = ServiceDepartment.objects.all().order_by('id')
        
        if user.is_system_admin():
            return qs
        # For service department roles, show only their own department
        if user.has_any_role([Roles.SERVICE_DEPT_ADMIN, Roles.SERVICE_DEPT_STAFF]):
            dept_id = getattr(user.service_department_id, 'id', None)
            if dept_id:
                return qs.filter(id=dept_id)
            return qs.none()
        # Others see nothing (but they won't pass permission anyway)
        return qs.none()
    
    def get_permissions(self):
        # List and retrieve: require authenticated and permission to view own dept(or system admin)
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated(), IsOwnServiceDepartment()]
        # Create, destroy: only System Admin
        if self.action in ['create', 'destroy']:
            return [IsAuthenticated(), IsSystemAdmin()]
        # Update, partial_update: System Admin (full) or Dept Admin (restricted via serializer)
        return [IsAuthenticated(), IsOwnServiceDepartment()]

    def destroy(self, request, *args, **kwargs):
        """
        Soft delete (Deactivate) - only System Admin can call this (permission enforced).
        """
        department = self.get_object()
        department.status = "INACTIVE"
        department.save()

        return Response(
            {"message": "Service Department deactivated successfully."},
            status=status.HTTP_200_OK
        )