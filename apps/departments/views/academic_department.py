from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.db import transaction
from django.http import HttpResponse
from django.db.models import Q
import openpyxl
from apps.departments.models import AcademicDepartment
from apps.departments.serializers import AcademicDepartmentSerializer
from apps.accounts.models import User
from apps.accounts.permissions import IsSystemAdmin
from apps.accounts.role_constants import Roles
from common.pagination import StandardPagination
from apps.audit.models import AuditLog


class AcademicDepartmentViewSet(viewsets.ModelViewSet):

    serializer_class = AcademicDepartmentSerializer
    pagination_class = StandardPagination
    permission_classes = [IsAuthenticated, IsSystemAdmin]

    def get_queryset(self):
        qs = AcademicDepartment.objects.exclude(status="INACTIVE").order_by("code")

        search = self.request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(code__icontains=search)
                | Q(stream__icontains=search)
                | Q(degree__icontains=search)
                | Q(branch__icontains=search)
                | Q(type__icontains=search)
                | Q(category__icontains=search)
            )

        for field in ("code", "stream", "degree", "branch", "type", "category"):
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
                changes[key] = {'old': old_value, 'new': new_value}

        if changes:
            AuditLog.log(
                request=self.request,
                action='UPDATE',
                obj=updated_instance,
                changes=changes
            )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        snapshot = self.get_serializer(instance).data
        object_id = instance.pk
        instance.delete()
        AuditLog.log(
            request=request,
            action='DELETE',
            obj=instance,
            object_id=object_id,
            changes=snapshot
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"], url_path="options")
    def get_options(self, request):

        base_qs = AcademicDepartment.objects.exclude(status="INACTIVE")
        types = list(base_qs.exclude(type="").values_list("type", flat=True).distinct())
        categories = list(base_qs.exclude(category="").values_list("category", flat=True).distinct())
        codes = list(base_qs.exclude(code="").values_list("code", flat=True).distinct())
        streams = list(base_qs.exclude(stream="").values_list("stream", flat=True).distinct())
        degrees = list(base_qs.exclude(degree="").values_list("degree", flat=True).distinct())
        branches = list(base_qs.exclude(branch="").values_list("branch", flat=True).distinct())
        
        return Response({
            "types": [{"value": x, "label": x} for x in types],
            "categories": [{"value": x, "label": x} for x in categories],
            "codes": [{"value": x, "label": x} for x in codes],
            "streams": [{"value": x, "label": x} for x in streams],
            "degrees": [{"value": x, "label": x} for x in degrees],
            "branches": [{"value": x, "label": x} for x in branches],
        })

    @action(detail=False, methods=['get'], url_path='export')
    def export_excel(self, request):
        qs = self.get_queryset()
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Academic Departments"
        
        headers = ["Code", "Stream", "Degree", "Branch", "Type", "Category"]
        ws.append(headers)
        
        for dept in qs:
            ws.append([
                dept.code,
                dept.stream,
                dept.degree,
                dept.branch,
                dept.type,
                dept.category,
            ])
            
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=academic_departments.xlsx'
        wb.save(response)
        
        return response

    @action(detail=False, methods=['post'], url_path='import', parser_classes=[MultiPartParser, FormParser])
    def import_excel(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            wb = openpyxl.load_workbook(file, data_only=True)
            ws = wb.active
        except Exception:
            return Response({"error": "Invalid Excel file format"}, status=status.HTTP_400_BAD_REQUEST)

        rows = list(ws.iter_rows(values_only=True))
        if len(rows) < 2:
            return Response({"error": "File is empty or contains only headers"}, status=status.HTTP_400_BAD_REQUEST)

        headers = [str(h).strip() for h in rows[0] if h is not None]
        expected_headers = ["Code", "Stream", "Degree", "Branch", "Type", "Category"]
        
        if len(headers) < len(expected_headers) or headers[:len(expected_headers)] != expected_headers:
            return Response({
                "error": f"Invalid headers. Expected: {', '.join(expected_headers)}"
            }, status=status.HTTP_400_BAD_REQUEST)

        errors = []
        valid_departments = []
        db_existing_pairs = set(AcademicDepartment.objects.values_list('code', 'stream'))
        seen_pairs_in_file = set()
        stream_map = {'SF-MEN': 'SFM', 'SF-WOMEN': 'SFW', 'SFM': 'SFM', 'SFW': 'SFW', 'AIDED': 'Aided'}
        allowed_streams = {'SFM', 'SFW', 'Aided'}

        for row_idx, row in enumerate(rows[1:], start=2):
            if not any(row):
                continue
                
            code = str(row[0]).strip().upper() if row[0] is not None else ""
            raw_stream = str(row[1]).strip() if row[1] is not None else ""
            stream = stream_map.get(raw_stream.upper(), raw_stream)
            degree = str(row[2]).strip() if row[2] is not None else ""
            branch = str(row[3]).strip() if row[3] is not None else ""
            dept_type = str(row[4]).strip() if row[4] is not None else ""
            category = str(row[5]).strip() if row[5] is not None else ""

            row_errors = []
            if not stream:
                row_errors.append("Stream is required.")
            elif stream not in allowed_streams:
                row_errors.append(f"Invalid Stream '{raw_stream}'. Allowed values: SFM, SFW, Aided.")

            pair = (code, stream)
            if not code:
                row_errors.append("Department Code is required.")
            elif len(code) > 20:
                row_errors.append("Department Code cannot exceed 20 characters.")
            elif pair in db_existing_pairs:
                row_errors.append(f"Department Code '{code}' with Stream '{stream}' already exists.")
            elif pair in seen_pairs_in_file:
                row_errors.append(f"Duplicate Department Code '{code}' with Stream '{stream}' found within the uploaded Excel file.")
            else:
                seen_pairs_in_file.add(pair)

            if not degree:
                row_errors.append("Degree is required.")
            elif len(degree) > 50:
                row_errors.append("Degree exceeds the maximum allowed length.")

            if not branch:
                row_errors.append("Branch is required.")
            elif len(branch) > 100:
                row_errors.append("Branch exceeds the maximum allowed length.")

            if not dept_type:
                row_errors.append("Type is required.")
            elif len(dept_type) > 100:
                row_errors.append("Type exceeds the maximum allowed length.")

            if not category:
                row_errors.append("Category is required.")
            elif len(category) > 100:
                row_errors.append("Category exceeds the maximum allowed length.")

            if row_errors:
                errors.append({"row": row_idx, "errors": row_errors})
            else:
                valid_departments.append(AcademicDepartment(
                    code=code,
                    stream=stream,
                    degree=degree,
                    branch=branch,
                    type=dept_type,
                    category=category,
                ))

        if errors:
            return Response({
                "error": "Validation failed for some rows",
                "details": errors
            }, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            AcademicDepartment.objects.bulk_create(valid_departments)
            AuditLog.log(
                request=request,
                action='IMPORT',
                obj=AcademicDepartment,
                object_id='BULK_IMPORT',
                object_repr='Imported Academic Departments',
                changes={"imported_count": len(valid_departments)}
            )

        return Response({
            "message": f"Successfully imported {len(valid_departments)} departments"
        }, status=status.HTTP_201_CREATED)