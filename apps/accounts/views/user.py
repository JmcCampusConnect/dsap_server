import openpyxl
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets, filters
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.audit.models import AuditLog
from ..models import User
from ..permissions import IsOwnServiceDepartment, IsUserManager
from ..role_constants import Roles
from ..serializers import UserSerializer, ResetPasswordSerializer

class UserViewSet(viewsets.ModelViewSet):
    serializer_class = UserSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["username","email"]

    # ------------------------------------------------------------------
    # Permissions
    # ------------------------------------------------------------------
    def get_permissions(self):
        # me: any authenticated user; reads: dept-scoped; mutations: admin + dept-scoped.
        if self.action == "me":
            return [IsAuthenticated()]

        if self.action in ("list", "retrieve", "export_excel"):
            return [IsAuthenticated(), IsOwnServiceDepartment()]

        return [IsAuthenticated(), IsUserManager(), IsOwnServiceDepartment()]

    # ------------------------------------------------------------------
    # Queryset
    # ------------------------------------------------------------------
    def get_queryset(self):
        """
        Role-scoped queryset used by list/export.

        The `service_department_id` query param is ONLY honoured for
        SYSTEM_ADMIN. Department-scoped roles are pinned to their own
        department regardless of any client-supplied value.
        """
        user = self.request.user
        qs = (
            User.objects.select_related(
                "role_id", "service_department_id", "academic_department_id"
            )
            .exclude(role_id__name=Roles.STUDENT)
            .all()
            .order_by("id")
        )
        
        # Query-param filters reused by every scoped branch below.
        role_id = self.request.query_params.get("role_id")
        is_active = self.request.query_params.get("is_active")
        
        # --- SYSTEM_ADMIN: full visibility, optional filters -----------
        if user.is_system_admin():
            service_dept_id = self.request.query_params.get("service_department_id")
            if service_dept_id:
                qs = qs.filter(service_department_id_id=service_dept_id)
            if role_id:
                qs = qs.filter(role_id_id=role_id)
            if is_active is not None:
                qs = qs.filter(is_active=is_active.lower() == "true")
            return qs
        
        # --- SERVICE_DEPT_ADMIN: own dept only, self excluded ---
        if user.has_role(Roles.SERVICE_DEPT_ADMIN):
            user_dept = getattr(user, "service_department_id", None)
            user_dept_id = getattr(user_dept, "id", None) if user_dept else None

            if user_dept_id is None:
                # Misconfigured admin — fall back to showing only self
                qs = qs.filter(id=user.id)
            else:
                qs = qs.filter(service_department_id_id=user_dept_id).exclude(id=user.id)

            if role_id:
                qs = qs.filter(role_id_id=role_id)
            if is_active is not None:
                qs = qs.filter(is_active=is_active.lower() == "true")
            return qs

        # --- SERVICE_DEPT_STAFF: own dept only, self included ---
        if user.has_role(Roles.SERVICE_DEPT_STAFF):
            user_dept = getattr(user, "service_department_id", None)
            user_dept_id = getattr(user_dept, "id", None) if user_dept else None

            if user_dept_id is None:
                qs = qs.filter(id=user.id)
            else:
                qs = qs.filter(service_department_id_id=user_dept_id)

            if role_id:
                qs = qs.filter(role_id_id=role_id)
            if is_active is not None:
                qs = qs.filter(is_active=is_active.lower() == "true")
            return qs
        
        # --- Any other role (students, teaching staff): self only -------
        return qs.filter(id=user.id)
    
    def get_object(self):
        """
        Resolve a user by pk from the *unscoped* table so out-of-scope
        access is denied with 403 (via object permission) instead of
        being masked by a 404. List scoping still lives in get_queryset.
        """
        queryset = User.objects.select_related(
            "role_id", "service_department_id", "academic_department_id"
        ).all()
        
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}
        
        obj = get_object_or_404(queryset, **filter_kwargs)
        self.check_object_permissions(self.request, obj)
        return obj
    
    # ------------------------------------------------------------------
    # Mutations (audit trail preserved)
    # ------------------------------------------------------------------
    def perform_create(self, serializer):
        instance = serializer.save()

        AuditLog.log(
            request=self.request,
            action="CREATE",
            obj=instance,
            changes=self.get_serializer(instance).data,
        )

    def perform_update(self, serializer):
        instance = self.get_object()
        old_data = self.get_serializer(instance).data
        updated_instance = serializer.save()
        new_data = self.get_serializer(updated_instance).data

        changes = {
            key: {"old": old_data.get(key), "new": new_value}
            for key, new_value in new_data.items()
            if old_data.get(key) != new_value
        }

        if changes:
            
            AuditLog.log(
                request=self.request,
                action="UPDATE",
                obj=updated_instance,
                changes=changes,
            )
            
    def perform_destroy(self, instance):
        if instance.id == self.request.user.id:
            raise PermissionDenied("Cannot deactivate self.")

        old_status = instance.is_active
        instance.is_active = False
        instance.save()

        AuditLog.log(
            request=self.request,
            action="DEACTIVATE",
            obj=instance,
            changes={"is_active": {"old": old_status, "new": False}},
        )

    # ------------------------------------------------------------------
    # Export (inherits scoping from get_queryset)
    # ------------------------------------------------------------------

    @action(detail=False, methods=["get"], url_path="export")
    def export_excel(self, request):
        qs = self.get_queryset().select_related("role_id")

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Users"

        ws.append(["Username", "Email", "Role", "Status"])

        for user in qs:
            ws.append(
                [
                    user.username,
                    user.email,
                    user.role_id.name if user.role_id else "",
                    "Active" if user.is_active else "Inactive",
                ]
            )

        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = "attachment; filename=users.xlsx"
        wb.save(response)

        AuditLog.log(
            request=request,
            action="EXPORT",
            obj=User,
            object_id="EXPORT_USERS",
            object_repr="Exported Users",
            changes={"exported_count": qs.count()},
        )

        return response
    
    # ------------------------------------------------------------------
    # Import (Excel/CSV)
    # ------------------------------------------------------------------
    @action(
        detail=False,
        methods=["post"],
        url_path="import",
        parser_classes=[MultiPartParser, FormParser],
    )
    def import_excel(self, request):
        """
        SYSTEM_ADMIN       : existing behaviour (no department assigned from file).
        SERVICE_DEPT_ADMIN : every imported user is forced into the admin's own
        department; only SERVICE_DEPT_STAFF role allowed.
        SERVICE_DEPT_STAFF : 403.
        """
        if not request.user.has_any_role(
            [Roles.SYSTEM_ADMIN, Roles.SERVICE_DEPT_ADMIN]
        ):
            return Response(
                {"error": "You do not have permission to import users."},
                status=status.HTTP_403_FORBIDDEN,
            )
            
        # Force department assignment for dept admins - never trust the file.
        forced_service_dept = None
        if request.user.has_role(Roles.SERVICE_DEPT_ADMIN):
            forced_service_dept = request.user.service_department_id
            if forced_service_dept is None:
                return Response(
                    {"error": "Your account is not assigned to a service department."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        file = request.FILES.get("file")

        if not file:
            return Response(
                {"error": "No file uploaded"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            wb = openpyxl.load_workbook(file, data_only=True)
            ws = wb.active
        except Exception:
            return Response(
                {"error": "Invalid Excel file format"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        rows = list(ws.iter_rows(values_only=True))

        if len(rows) < 2:
            return Response(
                {"error": "File is empty or contains only headers"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        headers = [str(h).strip() for h in rows[0] if h is not None]

        expected_headers = [
            "Username",
            "Email",
            "Role",
            "Status",
        ]

        if (
            len(headers) < len(expected_headers)
            or headers[: len(expected_headers)] != expected_headers
        ):
            return Response(
                {
                    "error": (
                        f"Invalid headers. Expected: "
                        f"{', '.join(expected_headers)}"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        errors = []
        valid_users = []

        db_existing_usernames = set(
            User.objects.values_list("username", flat=True)
        )
        db_existing_emails = set(
            User.objects.exclude(email__isnull=True)
            .exclude(email="")
            .values_list("email", flat=True)
        )

        seen_usernames = set()
        seen_emails = set()

        roles = {
            role.name: role
            for role in User._meta.get_field("role_id").remote_field.model.objects.all()
        }

        for row_idx, row in enumerate(rows[1:], start=2):
            if not any(row):
                continue

            username = (
                str(row[0]).strip()
                if row[0] is not None
                else ""
            )

            email = (
                str(row[1]).strip()
                if len(row) > 1 and row[1] is not None
                else ""
            )

            role_name = (
                str(row[2]).strip()
                if len(row) > 2 and row[2] is not None
                else ""
            )

            status_value = (
                str(row[3]).strip().lower()
                if len(row) > 3 and row[3] is not None
                else "active"
            )

            row_errors = []

            # Username validation
            if not username:
                row_errors.append("Username is required.")
            elif len(username) > 100:
                row_errors.append(
                    "Username cannot exceed 100 characters."
                )
            elif username in db_existing_usernames:
                row_errors.append(
                    f"Username '{username}' already exists."
                )
            elif username in seen_usernames:
                row_errors.append(
                    f"Duplicate Username '{username}' found within the uploaded Excel file."
                )
            else:
                seen_usernames.add(username)

            # Email validation
            if not email:
                row_errors.append("Email is required.")
            elif len(email) > 150:
                row_errors.append(
                    "Email cannot exceed 150 characters."
                )
            elif email in db_existing_emails:
                row_errors.append(
                    f"Email '{email}' already exists."
                )
            elif email in seen_emails:
                row_errors.append(
                    f"Duplicate Email '{email}' found within the uploaded Excel file."
                )
            else:
                seen_emails.add(email)

            # Role validation
            role_obj = None

            if not role_name:
                row_errors.append("Role is required.")
            elif role_name not in roles:
                row_errors.append(
                    f"Role '{role_name}' does not exist."
                )
            else:
                role_obj = roles[role_name]
                
            # Students are managed via Student Management, not here.
            if role_obj is not None and role_obj.name == Roles.STUDENT:
                row_errors.append(
                    "Student accounts must be created via Student Management."
                )
                
            # SERVICE_DEPT_ADMIN may only import SERVICE_DEPT_STAFF.
            if (
                request.user.has_role(Roles.SERVICE_DEPT_ADMIN)
                and role_obj is not None
                and role_obj.name != Roles.SERVICE_DEPT_STAFF
            ):
                row_errors.append(
                    "Service Dept Admin can only import users with role "
                    "'SERVICE_DEPT_STAFF'."
                )


            # Status validation
            if status_value not in {"active", "inactive"}:
                row_errors.append(
                    "Status must be active or inactive."
                )

            if row_errors:
                errors.append(
                    {
                        "row": row_idx,
                        "errors": row_errors,
                    }
                )
            else:
                valid_users.append(
                    User(
                        username=username,
                        email=email,
                        password_hash="",
                        role_id=role_obj,
                        is_active=status_value == "active",
                        service_department_id=forced_service_dept
                    )
                )

        if errors:
            return Response(
                {
                    "error": "Validation failed for some rows",
                    "details": errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            User.objects.bulk_create(valid_users)

            AuditLog.log(
                request=request,
                action="IMPORT",
                obj=User,
                object_id="BULK_IMPORT",
                object_repr="Imported Users",
                changes={
                    "imported_count": len(valid_users)
                },
            )

        return Response(
            {
                "message": (
                    f"Successfully imported "
                    f"{len(valid_users)} users"
                )
            },
            status=status.HTTP_201_CREATED,
        )
        
    # ------------------------------------------------------------------
    # Self-service
    # ------------------------------------------------------------------
    @action(detail=False, methods=["get"], url_path="me")
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    # ------------------------------------------------------------------
    # Password reset / activate (scoped via get_object + permissions)
    # ------------------------------------------------------------------
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

        AuditLog.log(
            request=request,
            action="UPDATE",
            obj=user,
            changes={
                "password": "Password reset"
            },
        )

        return Response(
            {"message": "Password reset successfully."},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"], url_path="activate")
    def activate(self, request, pk=None):
        user = self.get_object()

        old_status = user.is_active
        user.is_active = True
        user.save()

        AuditLog.log(
            request=request,
            action="ACTIVATE",
            obj=user,
            changes={
                "is_active": {
                    "old": old_status,
                    "new": True,
                }
            },
        )

        return Response(
            {"message": "User activated successfully."},
            status=status.HTTP_200_OK,
        )
