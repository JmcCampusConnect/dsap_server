from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from django.db.models import Q

from apps.services.models import Service, ServiceField
from apps.departments.models import ServiceDepartment
from apps.services.serializers import ServiceSerializer, ServiceFieldSerializer
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
                | Q(service_department_id__name__icontains=search)
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
        serializer.save(code=code, status="ACTIVE")

    # ── Soft-delete (toggle ACTIVE <-> INACTIVE) ─────────────────
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status == "ACTIVE":
            instance.status = "INACTIVE"
        else:
            instance.status = "ACTIVE"
        instance.save()
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
        
        return Response({
            "departments": dept_options, 
            "statuses": status_options,
            "codes": code_options,
            "names": name_options
        })

    # ── Public directory (active only) ───────────────────────────
    @action(detail=False, methods=["get"], url_path="public")
    def public_list(self, request):
        qs = (
            Service.objects.select_related("service_department_id")
            .filter(status="ACTIVE")
            .order_by("service_department_id__name", "code")
        )
        serializer = ServiceSerializer(qs, many=True)
        return Response(serializer.data)


class ServiceFieldViewSet(viewsets.ModelViewSet):
    """
    CRUD for service fields (Admin only).
    Routes are nested under /api/services/{service_id}/fields/
    """
    serializer_class = ServiceFieldSerializer
    pagination_class = StandardPagination

    def get_permissions(self):
        return [AllowAny()]

    def get_queryset(self):
        service_id = self.kwargs.get("service_id")
        qs = ServiceField.objects.filter(service_id=service_id).order_by("display_order", "id")
        return qs

    def perform_create(self, serializer):
        service_id = self.kwargs.get("service_id")
        try:
            service = Service.objects.get(id=service_id)
        except Service.DoesNotExist:
            return Response({"detail": "Service not found"}, status=status.HTTP_404_NOT_FOUND)
        
        # Calculate next display order if not provided
        display_order = serializer.validated_data.get("display_order", 0)
        if display_order == 0:
            last_field = ServiceField.objects.filter(service_id=service_id).order_by("-display_order").first()
            display_order = (last_field.display_order + 1) if last_field else 1
            
        serializer.save(service_id=service, display_order=display_order)

    @action(detail=False, methods=["patch"], url_path="reorder")
    def reorder(self, request, service_id=None):
        """
        Expects a list of objects with { id: <int>, display_order: <int> }
        """
        fields_data = request.data
        if not isinstance(fields_data, list):
            return Response({"detail": "Expected a list of field orders"}, status=status.HTTP_400_BAD_REQUEST)
        
        updated_fields = []
        for item in fields_data:
            field_id = item.get("id")
            display_order = item.get("display_order")
            if field_id is not None and display_order is not None:
                try:
                    field = ServiceField.objects.get(id=field_id, service_id=service_id)
                    field.display_order = display_order
                    updated_fields.append(field)
                except ServiceField.DoesNotExist:
                    continue
                    
        # Bulk update
        if updated_fields:
            ServiceField.objects.bulk_update(updated_fields, ["display_order"])
            
        return Response({"detail": "Reordered successfully"})
