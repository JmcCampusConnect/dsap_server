from rest_framework import viewsets, status, serializers
from rest_framework.viewsets import GenericViewSet
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from django.db.models import Q, Count
from django.shortcuts import get_object_or_404

from apps.audit.models import AuditLog
from apps.services.models import Service, ServiceField, ServiceDocument
from apps.departments.models import ServiceDepartment
from apps.accounts.models import Role
from apps.workflow.constants import ACTION_TYPE_CHOICES, ALLOWED_ACTION_CHOICES
from apps.services.serializers import (
    ServiceSerializer, 
    ServiceFieldSerializer, 
    ServiceDocumentSerializer,
    ServiceDetailSerializer,
    ServiceDirectoryDepartmentSerializer,
    ServiceDepartmentWithCountSerializer,
)
from common.pagination import StandardPagination


class ServiceViewSet(viewsets.ModelViewSet):
    """
    CRUD for services.

    list / retrieve        -> any authenticated user (AllowAny for dev)
    create / update        -> system_admin / service_dept_admin
    destroy (soft-delete)  -> toggles status ACTIVE <-> INACTIVE
    options_list           -> dropdown data for forms
    public_list            -> public directory (active services only)
    """

    serializer_class = ServiceSerializer
    pagination_class = StandardPagination

    # ── Permissions ──────────────────────────────────────────────
    def get_permissions(self):
        # TODO: Replace with [IsSystemAdmin | IsServiceDeptAdmin] in production
        return [AllowAny()]

    # ── QuerySet ─────────────────────────────────────────────────
    def get_queryset(self):
        qs = Service.objects.select_related("service_department_id").order_by(
            "-created_at"
        )

        search = self.request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(code__icontains=search)
                | Q(name__icontains=search)
                | Q(service_department__name__icontains=search)
            )

        status_filter = self.request.query_params.get("status", "").strip()
        if status_filter:
            qs = qs.filter(status=status_filter)

        dept_filter = self.request.query_params.get("department", "").strip()
        if dept_filter:
            qs = qs.filter(service_department_id=dept_filter)

        code_filter = self.request.query_params.get("code", "").strip()
        if code_filter:
            qs = qs.filter(code__icontains=code_filter)

        name_filter = self.request.query_params.get("name", "").strip()
        if name_filter:
            qs = qs.filter(name__icontains=name_filter)

        return qs

    # ── Create (auto-generate code) ──────────────────────────────
    def perform_create(self, serializer):
        dept = serializer.validated_data["service_department_id"]
        prefix = dept.code

        # Find next available sequence number for this prefix
        existing_codes = (
            Service.objects.filter(code__startswith=f"{prefix}-")
            .values_list("code", flat=True)
        )
        max_seq = 0
        for c in existing_codes:
            try:
                seq = int(c.split("-")[-1])
                if seq > max_seq:
                    max_seq = seq
            except (ValueError, IndexError):
                pass

        code = f"{prefix}-{str(max_seq + 1).zfill(3)}"
        instance = serializer.save(code=code, status="ACTIVE")
        AuditLog.log(
            request=self.request,
            action="CREATE",
            obj=instance,
            changes=self.get_serializer(instance).data,
        )

    def perform_update(self, serializer):
        old_data = self.get_serializer(serializer.instance).data
        updated_instance = serializer.save()
        new_data = self.get_serializer(updated_instance).data
        changes = {}
        for key, new_value in new_data.items():
            old_value = old_data.get(key)
            if old_value != new_value:
                changes[key] = {"old": old_value, "new": new_value}
        AuditLog.log(
            request=self.request,
            action="UPDATE",
            obj=updated_instance,
            changes=changes,
        )

    # ── Soft-delete (toggle ACTIVE <-> INACTIVE) ─────────────────
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        old_status = instance.status
        if instance.status == "ACTIVE":
            instance.status = "INACTIVE"
        else:
            instance.status = "ACTIVE"
        instance.save()
        AuditLog.log(
            request=request,
            action="UPDATE",
            obj=instance,
            changes={"status": {"old": old_status, "new": instance.status}},
        )
        return Response(ServiceSerializer(instance).data)

    # ── Dropdown options ─────────────────────────────────────────
    @action(detail=False, methods=["get"], url_path="options")
    def options_list(self, request):
        departments = ServiceDepartment.objects.filter(status="ACTIVE").order_by("name")
        dept_options = [
            {"value": str(dept.id), "label": dept.name} for dept in departments
        ]
        status_options = [
            {"value": "ACTIVE", "label": "Active"},
            {"value": "INACTIVE", "label": "Inactive"},
        ]
        
        codes = Service.objects.values_list('code', flat=True).distinct().order_by('code')
        names = Service.objects.values_list('name', flat=True).distinct().order_by('name')
        
        code_options = [{"value": c, "label": c} for c in codes if c]
        name_options = [{"value": n, "label": n} for n in names if n]

        roles = Role.objects.all().order_by("name")
        role_options = [
            {
                "value": str(r.id),
                "label": r.name,
                "description": r.description,
            }
            for r in roles
        ]

        action_type_options = [
            {"value": code, "label": label} for code, label in ACTION_TYPE_CHOICES
        ]
        allowed_action_options = [
            {"value": code, "label": label} for code, label in ALLOWED_ACTION_CHOICES
        ]
        
        return Response({
            "departments": dept_options, 
            "statuses": status_options,
            "codes": code_options,
            "names": name_options,
            "roles": role_options,
            "action_types": action_type_options,
            "allowed_actions": allowed_action_options,
        })

    # ── Public directory (active only) ───────────────────────────
    @action(detail=False, methods=["get"], url_path="public") 
    def public_list(self, request):
        qs = (
            Service.objects.select_related("service_department_id")
            .filter(status="ACTIVE")
            .order_by("service_department__name", "code")
        )
        serializer = ServiceSerializer(qs, many=True)
        return Response(serializer.data)
    
    # -------- public directory endpoints --------
    @action(detail=False, methods=['get'], url_path='directory')
    def directory(self, request):
        """
        List all enabled services grouped by department.
        """
        departments = ServiceDepartment.objects.filter(
            service__status='ENABLED'
        ).distinct().order_by('name')
        serializer = ServiceDirectoryDepartmentSerializer(departments, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='detail')
    def detail_with_fields(self, request, pk=None):
        """
        Get full service detail with fields and documents.
        Only if service is ENABLED.
        """
        service = self.get_queryset().filter(status='ENABLED').first()
        if not service:
            return Response(
                {'detail': 'Service not found or not enabled.'},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = ServiceDetailSerializer(service)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='departments')
    def department_list(self, request):
        """
        List departments with count of enabled services.
        """
        departments = ServiceDepartment.objects.annotate(
            service_count=Count('service', filter=Q(service__status='ENABLED'))
        ).filter(service_count__gt=0).order_by('name')
        serializer = ServiceDepartmentWithCountSerializer(departments, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='search')
    def search(self, request):
        """
        Search enabled services by query string (q).
        Searches in name, code, and description (if available).
        """
        query = request.query_params.get('q', '').strip()
        if not query:
            return Response(
                {'detail': 'Please provide a search query using ?q='},
                status=status.HTTP_400_BAD_REQUEST
            )
        services = Service.objects.filter(status='ENABLED')
        # Use Q to search in name, code, and description (if field exists)
        q_objects = Q(name__icontains=query) | Q(code__icontains=query)
        if hasattr(Service, 'description'):
            q_objects |= Q(description__icontains=query)
        services = services.filter(q_objects).order_by('name')
        serializer = ServiceSerializer(services, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='filter')
    def filter_by_department(self, request):
        """
        Filter enabled services by department ID.
        """
        dept_id = request.query_params.get('department', '').strip()
        if not dept_id:
            return Response(
                {'detail': 'Please provide department ID using ?department='},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            dept_id = int(dept_id)
        except ValueError:
            return Response(
                {'detail': 'Invalid department ID.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        services = Service.objects.filter(
            status='ENABLED',
            service_department_id=dept_id
        ).order_by('name')
        serializer = ServiceSerializer(services, many=True)
        return Response(serializer.data)


class ServiceFieldViewSet(viewsets.ModelViewSet):
    """
    CRUD for service fields (Admin only).
    Routes are nested under /api/services/{service_id}/fields/
    """
    serializer_class = ServiceFieldSerializer
    pagination_class = StandardPagination

    def get_permissions(self):
        # TODO: Replace with proper admin permissions
        return [AllowAny()]

    def get_queryset(self):
        """Get fields for a specific service"""
        service_id = self.kwargs.get("service_id")
        if not service_id:
            return ServiceField.objects.none()
        return ServiceField.objects.filter(service_id=service_id).order_by("display_order", "id")

    def perform_create(self, serializer):
        """Create a new field with auto-incrementing display_order"""
        service_id = self.kwargs.get("service_id")
        service = get_object_or_404(Service, id=service_id)
        
        # Calculate next display order if not provided
        display_order = serializer.validated_data.get("display_order", 0)
        if display_order == 0:
            last_field = ServiceField.objects.filter(service_id=service_id).order_by("-display_order").first()
            display_order = (last_field.display_order + 1) if last_field else 1
        
        instance = serializer.save(service_id=service, display_order=display_order)
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
        changes = {}
        for key, new_value in new_data.items():
            old_value = old_data.get(key)
            if old_value != new_value:
                changes[key] = {"old": old_value, "new": new_value}
        AuditLog.log(
            request=self.request,
            action="UPDATE",
            obj=updated_instance,
            changes=changes,
        )

    @action(detail=False, methods=["patch"], url_path="reorder")
    def reorder(self, request, service_id=None):
        """
        Expects a list of objects with { id: <int>, display_order: <int> }
        """
        fields_data = request.data
        if not isinstance(fields_data, list):
            return Response(
                {"detail": "Expected a list of field orders"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        updated_fields = []
        errors = []
        
        for item in fields_data:
            field_id = item.get("id")
            display_order = item.get("display_order")
            
            if field_id is None or display_order is None:
                errors.append(f"Missing id or display_order for item: {item}")
                continue
                
            try:
                field = ServiceField.objects.get(id=field_id, service_id=service_id)
                field.display_order = display_order
                updated_fields.append(field)
            except ServiceField.DoesNotExist:
                errors.append(f"Field with id {field_id} not found in this service")
                continue
        
        if errors:
            return Response(
                {"detail": "Some fields could not be updated", "errors": errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Bulk update
        if updated_fields:
            ServiceField.objects.bulk_update(updated_fields, ["display_order"])
            AuditLog.log(
                request=request,
                action="UPDATE",
                app_label="services",
                model_name="ServiceField",
                changes={"reorder": fields_data},
            )
            
        return Response(
            {"detail": "Reordered successfully", "updated": len(updated_fields)},
            status=status.HTTP_200_OK
        )


class ServiceDocumentViewSet(viewsets.ModelViewSet):
    """
    CRUD for service documents.
    Nested under /api/services/<service_id>/documents/
    """
    serializer_class = ServiceDocumentSerializer
    pagination_class = None

    def get_permissions(self):
        # TODO: Replace with proper admin permissions
        return [AllowAny()]

    def get_queryset(self):
        """Get documents for a specific service"""
        service_id = self.kwargs.get("service_id")
        if not service_id:
            return ServiceDocument.objects.none()
        return ServiceDocument.objects.filter(service_id=service_id).order_by("created_at")

    def perform_create(self, serializer):
        """Create a new document for a service"""
        service_id = self.kwargs.get("service_id")
        service = get_object_or_404(Service, id=service_id)
        instance = serializer.save(service_id=service)
        AuditLog.log(
            request=self.request,
            action="CREATE",
            obj=instance,
            changes=self.get_serializer(instance).data,
        )

    def perform_update(self, serializer):
        """Update a document"""
        service_id = self.kwargs.get("service_id")
        # Ensure the document belongs to the correct service
        instance = self.get_object()
        if str(instance.service_id_id) != str(service_id):
            raise serializers.ValidationError(
                "Document does not belong to this service"
            )
        old_data = self.get_serializer(instance).data
        updated_instance = serializer.save()
        new_data = self.get_serializer(updated_instance).data
        changes = {}
        for key, new_value in new_data.items():
            old_value = old_data.get(key)
            if old_value != new_value:
                changes[key] = {"old": old_value, "new": new_value}
        AuditLog.log(
            request=self.request,
            action="UPDATE",
            obj=updated_instance,
            changes=changes,
        )

    def destroy(self, request, *args, **kwargs):
        """Delete a document"""
        instance = self.get_object()
        service_id = self.kwargs.get("service_id")
        
        # Ensure the document belongs to the correct service
        if str(instance.service_id_id) != str(service_id):
            return Response(
                {"detail": "Document does not belong to this service"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        object_id = instance.id
        snapshot = self.get_serializer(instance).data
        instance.delete()
        AuditLog.log(
            request=request,
            action="DELETE",
            obj=instance,
            object_id=object_id,
            changes=snapshot,
        )
        return Response(
            {"detail": "Document deleted successfully"},
            status=status.HTTP_204_NO_CONTENT
        )
        
class ServiceDirectoryViewSet(GenericViewSet):
    """
    Public service directory endpoints.
    Only returns services with status = 'ENABLED'.
    """
    permission_classes = [AllowAny]
    serializer_class = ServiceSerializer

    def get_queryset(self):
        return Service.objects.filter(status='ENABLED').select_related('service_department_id')

    @action(detail=False, methods=['get'], url_path='')
    def list_directory(self, request):
        """
        GET /api/service-directory/ - List all enabled services grouped by department.
        """
        departments = ServiceDepartment.objects.filter(
            service__status='ENABLED'
        ).distinct().order_by('name')
        serializer = ServiceDirectoryDepartmentSerializer(departments, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='detail')
    def detail_with_fields(self, request, pk=None):
        """
        GET /api/service-directory/{service_id}/ - Get service detail with fields/documents.
        """
        try:
            service = self.get_queryset().get(pk=pk)
        except Service.DoesNotExist:
            return Response(
                {'detail': 'Service not found or not enabled.'},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = ServiceDetailSerializer(service)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='departments')
    def department_list(self, request):
        """
        GET /api/service-directory/departments/ - List departments with service counts.
        """
        departments = ServiceDepartment.objects.annotate(
            service_count=Count('service', filter=Q(service__status='ENABLED'))
        ).filter(service_count__gt=0).order_by('name')
        serializer = ServiceDepartmentWithCountSerializer(departments, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='search')
    def search(self, request):
        """
        GET /api/service-directory/search/?q= - Search services.
        """
        query = request.query_params.get('q', '').strip()
        if not query:
            return Response(
                {'detail': 'Please provide a search query using ?q='},
                status=status.HTTP_400_BAD_REQUEST
            )
        services = self.get_queryset()
        q_objects = Q(name__icontains=query) | Q(code__icontains=query)
        if hasattr(Service, 'description'):
            q_objects |= Q(description__icontains=query)
        services = services.filter(q_objects).order_by('name')
        serializer = ServiceSerializer(services, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='filter')
    def filter_by_department(self, request):
        """
        GET /api/service-directory/filter/?department= - Filter by department.
        """
        dept_id = request.query_params.get('department', '').strip()
        if not dept_id:
            return Response(
                {'detail': 'Please provide department ID using ?department='},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            dept_id = int(dept_id)
        except ValueError:
            return Response(
                {'detail': 'Invalid department ID.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        services = self.get_queryset().filter(service_department_id=dept_id).order_by('name')
        serializer = ServiceSerializer(services, many=True)
        return Response(serializer.data)