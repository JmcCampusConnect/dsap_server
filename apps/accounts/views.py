from django.contrib.auth.models import User
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import viewsets, permissions, status
# from apps.accounts.models import User, Role
from apps.accounts.serializers import UserSerializer, RoleSerializer
from apps.accounts.permissions import IsSystemAdmin
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import AllowAny
from .serializers import CustomTokenObtainPairSerializer
from .serializers import LogoutSerializer




        





class UserViewSet(viewsets.ModelViewSet):
    """ User management - Only System Admin can access"""
    queryset = User.objects.all().order_by("id")
    serializer_class = UserSerializer
    permission_classes = [IsSystemAdmin]
    def destroy(self, request, *args, **kwargs):
        user = self.get_object()

        user.is_active = False
        user.save()

        return Response(
            {"message":"User deactivated successfully."},
            status=status.HTTP_200_OK,
        )
    
    @action(detail=True, methods=["patch"])
    def reset_password(self, request, pk=None):

        user = self.get_object()

        password = request.data.get("password")

        if not password:
            return Response(
                {
                    "error": "Password is required"
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(password)
        user.save()

        return Response(
            {
                "message": "Password reset successfully"
            },
            status=status.HTTP_200_OK
        )


class UserRoleViewSet(viewsets.ModelViewSet):
    """ Role management - Only System Admin can access """
    queryset = UserRole.objects.all()
    serializer_class = UserRoleSerializer
    permission_classes = [IsSystemAdmin] 

# class RoleViewSet(viewsets.ModelViewSet):
#     """ Role management - Only System Admin can access """
#     queryset = Role.objects.all()
#     serializer_class = RoleSerializer
#     permission_classes = [IsSystemAdmin]

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
    permission_classes = [AllowAny]

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
