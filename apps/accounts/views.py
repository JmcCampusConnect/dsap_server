from rest_framework import viewsets, permissions
from apps.accounts.models import User, UserRole
from apps.accounts.serializers import UserSerializer, UserRoleSerializer
from apps.accounts.permissions import IsSystemAdmin

class UserViewSet(viewsets.ModelViewSet):
    """ User management - Only System Admin can access"""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsSystemAdmin]


class UserRoleViewSet(viewsets.ModelViewSet):
    """ Role management - Only System Admin can access """
    queryset = UserRole.objects.all()
    serializer_class = UserRoleSerializer
    permission_classes = [IsSystemAdmin] 