from django.contrib.auth.hashers import make_password
from rest_framework import status, viewsets, filters
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from ..models import User
from ..serializers import (
    UserSerializer,
    ResetPasswordSerializer,
)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by("id")
    serializer_class = UserSerializer
    permission_classes = [AllowAny]

    filter_backends = [
        filters.SearchFilter,
    ]

    search_fields = [
        "username",
        "email",
    ]

    def get_queryset(self):
        queryset = User.objects.all().order_by("id")

        role_id = self.request.query_params.get("role_id")
        is_active = self.request.query_params.get("is_active")

        if role_id:
            queryset = queryset.filter(role_id_id=role_id)

        if is_active:
            queryset = queryset.filter(
                is_active=is_active.lower() == "true"
            )

        return queryset

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

    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, pk=None):
        user = self.get_object()
        user.is_active = True
        user.save()

        return Response(
            {"message": "User activated successfully."},
            status=status.HTTP_200_OK,
        )

    