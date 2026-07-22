from rest_framework import viewsets, permissions
from apps.accounts.models import User, Role
from apps.accounts.serializers import UserSerializer, RoleSerializer
from apps.accounts.permissions import IsSystemAdmin
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import AllowAny, IsAuthenticated
from .serializers import CustomTokenObtainPairSerializer
from .serializers import LogoutSerializer

class UserViewSet(viewsets.ModelViewSet):
    """ User management - Only System Admin can access"""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsSystemAdmin]


class RoleViewSet(viewsets.ModelViewSet):
    """ Role management - Only System Admin can access """
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [IsSystemAdmin]

# ====== ADD LOGIN VIEW ======
class LoginView(TokenObtainPairView):
    """
    POST /api/auth/login/
    Accepts username & password → returns JWT + role + menus.
    """
    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [AllowAny]

# ====== ADD LOGOUT VIEW ======
class LogoutView(APIView):
    """
    POST /api/auth/logout/
    Accepts refresh token → blacklists it.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # We'll use a simple serializer for validation
        serializer = LogoutSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        refresh_token = serializer.validated_data['refresh']
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({"detail": "Logged out successfully."},
                            status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response({"detail": str(e)},
                            status=status.HTTP_400_BAD_REQUEST)