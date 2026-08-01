from django.contrib.auth.hashers import make_password
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from ..models import User
from ..serializers import (
    UserSerializer,
    ResetPasswordSerializer,
)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by("id")
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()

    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password(self, request, pk=None):
        user = self.get_object()

        serializer = ResetPasswordSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        user.password_hash = make_password(
            serializer.validated_data["password"]
        )
        user.save()

        return Response(
            {"message": "Password reset successfully."},
            status=status.HTTP_200_OK,
        )