from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from django.db.models import Q

from apps.departments.models import AcademicDepartment
from apps.departments.serializers.academic_department import AcademicDepartmentSerializer
from common.pagination import StandardPagination
from common.models import AuditLog


class AcademicDepartmentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for CRUD operations on AcademicDepartment.

    Supports:
    - GET  /academic-departments/          — Paginated list with optional search + filters
    - POST /academic-departments/          — Create a new department
    - GET  /academic-departments/{id}/     — Retrieve a single department
    - PUT  /academic-departments/{id}/     — Full update
    - DEL  /academic-departments/{id}/     — Hard-delete
    - GET  /academic-departments/options/  — Distinct filter/dropdown values

    Search:
        ?search=<term>   Matches code, name, degree, branch, type, category (OR)

    Field filters (exact match, AND-combined with each other and search):
        ?code=<value>
        ?name=<value>
        ?degree=<value>
        ?branch=<value>
        ?type=<value>
        ?category=<value>

    Pagination:
        ?page=<n>         Page number (default: 1)
        ?page_size=<n>    Items per page (default: 10, max: 100)
    """

    serializer_class = AcademicDepartmentSerializer
    pagination_class = StandardPagination

    def get_permissions(self):
        """
        Temporarily AllowAny for frontend development.
        Replace with IsAuthenticated / role-based permissions before production.
        """
        return [AllowAny()]

    def get_queryset(self):
        """
        Return the base queryset with optional search and field-level filters.

        All active filter params are AND-combined:
          - ?search=<term> is a broad OR match across code/name/degree/branch/type/category
          - ?code=, ?name=, ?degree=, ?branch=, ?type=, ?category= are exact-match filters
        """
        qs = AcademicDepartment.objects.exclude(status="INACTIVE").order_by("code")

        # Broad text search (OR across all text fields)
        search = self.request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(code__icontains=search)
                | Q(name__icontains=search)
                | Q(degree__icontains=search)
                | Q(branch__icontains=search)
                | Q(type__icontains=search)
                | Q(category__icontains=search)
            )

        # Exact field-level filters (AND-combined)
        for field in ("code", "name", "degree", "branch", "type", "category"):
            val = self.request.query_params.get(field, "").strip()
            if val:
                qs = qs.filter(**{field: val})

        return qs

    def perform_create(self, serializer):
        instance = serializer.save()
        changes = self.get_serializer(instance).data
        
        AuditLog.log(
            request=self.request,
            action='CREATE',
            obj=instance,
            changes=changes
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
                changes[key] = {
                    'old': old_value,
                    'new': new_value
                }
                
        if changes:
            AuditLog.log(
                request=self.request,
                action='UPDATE',
                obj=updated_instance,
                changes=changes
            )

    def destroy(self, request, *args, **kwargs):
        """
        Hard-delete: permanently remove the department row from the database.
        Returns HTTP 204 No Content on success.

        The frontend RTK Query invalidates the LIST and OPTIONS cache tags
        after this returns, so the table and dropdowns refresh automatically.
        """
        instance = self.get_object()
        
        # 1. Capture object snapshot before deletion
        snapshot = self.get_serializer(instance).data
        
        # 2. Delete object
        instance.delete()
        
        # 3. Create audit record
        AuditLog.log(
            request=request,
            action='DELETE',
            obj=instance,
            changes=snapshot
        )
        
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"], url_path="options")
    def get_options(self, request):
        """
        Returns distinct values for all searchable/filterable fields.
        Used to populate the filter dropdowns and SearchableSelect options
        in the frontend.
        """
        base_qs = AcademicDepartment.objects.exclude(status="INACTIVE")

        types = list(
            base_qs.exclude(type="").values_list("type", flat=True).distinct()
        )
        categories = list(
            base_qs.exclude(category="").values_list("category", flat=True).distinct()
        )
        codes = list(
            base_qs.exclude(code="").values_list("code", flat=True).distinct()
        )
        names = list(
            base_qs.exclude(name="").values_list("name", flat=True).distinct()
        )
        degrees = list(
            base_qs.exclude(degree="").values_list("degree", flat=True).distinct()
        )
        branches = list(
            base_qs.exclude(branch="").values_list("branch", flat=True).distinct()
        )

        return Response(
            {
                "types": [{"value": x, "label": x} for x in types],
                "categories": [{"value": x, "label": x} for x in categories],
                "codes": [{"value": x, "label": x} for x in codes],
                "names": [{"value": x, "label": x} for x in names],
                "degrees": [{"value": x, "label": x} for x in degrees],
                "branches": [{"value": x, "label": x} for x in branches],
            }
        )
