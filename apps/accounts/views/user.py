from django.contrib.auth.hashers import make_password
from rest_framework import status, viewsets, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from ..models import User
from ..permissions import IsSystemAdmin, IsServiceDeptAdmin, IsSelfOrSystemAdmin
from ..role_constants import Roles
from ..serializers import UserSerializer, ResetPasswordSerializer


class UserViewSet(viewsets.ModelViewSet):
    serializer_class = UserSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["username","email"]

    def get_permissions(self):
        if self.action in ['me','retrieve']:
            return [IsAuthenticated()]
        if self.action in ['reset_password','activate']:
            return [IsAuthenticated(), IsSelfOrSystemAdmin()]
        return [IsAuthenticated(), (IsSystemAdmin | IsServiceDeptAdmin)()]

    def get_queryset(self):
        user = self.request.user
        qs = User.objects.select_related('role_id','service_department_id').all().order_by("id")
        if user.is_system_admin():
            role_id = self.request.query_params.get("role_id")
            is_active = self.request.query_params.get("is_active")
            if role_id:
                qs = qs.filter(role_id_id=role_id)
            if is_active is not None:
                qs = qs.filter(is_active=is_active.lower() == "true")
            return qs
        if user.has_role(Roles.SERVICE_DEPT_ADMIN):
            # Only own department + self
            dept_id = getattr(user.service_department_id, 'id', None) if user.service_department_id else None
            if dept_id:
                return qs.filter(service_department_id_id=dept_id)
            return qs.filter(id=user.id)
        # Staff/Student/Teaching can only see self
        return qs.filter(id=user.id)
    
    def get_object(self):
        obj = super().get_object()
        self.check_object_permissions(self.request, obj)
        return obj

    def perform_destroy(self, instance):
        if instance.id == self.request.user.id:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Cannot deactivate self")
        instance.is_active = False
        instance.save()

    @action(detail=False, methods=["get"], url_path="me")
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

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
