from rest_framework import viewsets
from ..models import Role
from ..permissions import IsSystemAdmin
from ..serializers import RoleSerializer


class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [IsSystemAdmin]