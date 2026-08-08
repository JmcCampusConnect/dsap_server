from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from ..models import Role
from ..permissions import IsSystemAdmin, IsServiceDeptAdmin
from ..serializers import RoleSerializer


class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.all().order_by("id")
    serializer_class = RoleSerializer
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated(), (IsSystemAdmin | IsServiceDeptAdmin)()]
        return [IsSystemAdmin()]