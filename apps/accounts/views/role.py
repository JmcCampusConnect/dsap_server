from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from ..models import Role
from ..permissions import IsSystemAdmin, IsServiceDeptAdmin
from ..role_constants import Roles
from ..serializers import RoleSerializer


class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.none()
    serializer_class = RoleSerializer
    
    def get_queryset(self):
        return Role.objects.filter(name__in=Roles.all()).order_by("id")

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated(), (IsSystemAdmin | IsServiceDeptAdmin)()]
        return [IsSystemAdmin()]