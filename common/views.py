from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from common.models import User
from common.serializers import UserSerializer

class UserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.filter(is_active=True)
    serializer_class = UserSerializer
    permission_classes = [AllowAny]
