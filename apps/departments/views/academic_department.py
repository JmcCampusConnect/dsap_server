import openpyxl
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import HttpResponse
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsSystemAdmin
from apps.audit.models import AuditLog
from apps.departments.models import AcademicDepartment
from apps.departments.serializers import AcademicDepartmentSerializer
from common.pagination import StandardPagination


class AcademicDepartmentViewSet(viewsets.ModelViewSet):
    serializer_class = AcademicDepartmentSerializer
    pagination_class = StandardPagination
    permission_classes = [IsAuthenticated, IsSystemAdmin]

    def get_queryset(self):

        status_filter = self.request.query_params.get("status", "").strip().lower()

        if status_filter == "active":
            qs = AcademicDepartment.objects.filter(status__iexact="active")
        elif status_filter == "inactive":
            qs = AcademicDepartment.objects.exclude(status__iexact="active")
        else:
            qs = AcademicDepartment.objects.all()

        qs = qs.order_by("code")
        search = self.request.query_params.get("search", "").strip()
        if search:
            for term in search.split():
                qs = qs.filter(
                    Q(code__icontains=term)
                    | Q(stream__icontains=term)
                    | Q(degree__icontains=term)
                    | Q(branch__icontains=term)
                    | Q(type__icontains=term)
                    | Q(category__icontains=term)
                )

        for field in ("code", "stream", "degree", "branch", "type", "category"):
            val = self.request.query_params.get(field, "").strip()
            if val and val.upper() != "ALL":
                qs = qs.filter(**{f"{field}__iexact": val})

        return qs


    def perform_create(self, serializer):
        try:
            with transaction.atomic():
                instance = serializer.save()
        except IntegrityError:
            raise serializers.ValidationError({
                "code": ["Academic department already exists."]
            })

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
        status_changed = False

        old_status = old_data.get('status', '').lower()
        new_status = new_data.get('status', '').lower()

        for key, new_value in new_data.items():
            old_value = old_data.get(key)

            if old_value != new_value:
                changes[key] = {
                    'old': old_value,
                    'new': new_value,
                }

                if key == 'status':
                    status_changed = True

        if status_changed and len(changes) == 1:
            if old_status == 'active' and new_status == 'inactive':
                action = 'DEACTIVATE'
            elif old_status == 'inactive' and new_status == 'active':
                action = 'ACTIVATE'
            else:
                action = 'UPDATE'
        else:
            action = 'UPDATE'

        if changes:
            AuditLog.log(
                request=self.request,
                action=action,
                obj=updated_instance,
                changes=changes,
            )

    def destroy(self, request, *args, **kwargs):
        """Soft delete (Deactivate) Academic Department."""
        instance = self.get_object()

        snapshot = self.get_serializer(instance).data
        object_id = instance.pk

        instance.status = 'inactive'
        instance.save(update_fields=['status', 'updated_at'])

        AuditLog.log(
            request=request,
            action='DEACTIVATE',
            obj=instance,
            object_id=object_id,
            changes=snapshot
        )

        return Response(
            {"message": "Academic Department deactivated successfully."},
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, pk=None):
        instance = self.get_object()

        current_status = str(instance.status or '').strip().lower()
        if current_status == 'active':
            return Response(
                {"detail": "Academic Department is already active."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Pre-check if another active department with the same (code, stream) exists
        conflict = AcademicDepartment.objects.filter(
            code__iexact=instance.code,
            stream__iexact=instance.stream,
            status__iexact='active'
        ).exclude(pk=instance.pk).first()

        if conflict:
            return Response(
                {
                    "detail": (
                        f"Cannot activate department '{instance.code}' ({instance.stream}) "
                        f"because an active department with this code and stream already exists."
                    )
                },
                status=status.HTTP_409_CONFLICT
            )

        old_status = instance.status
        instance.status = 'active'

        try:
            instance.save(update_fields=['status', 'updated_at'])
        except IntegrityError:
            return Response(
                {
                    "detail": (
                        f"Cannot activate department '{instance.code}' ({instance.stream}) "
                        f"due to a conflict with an existing record."
                    )
                },
                status=status.HTTP_409_CONFLICT
            )

        AuditLog.log(
            request=request,
            action='ACTIVATE',
            obj=instance,
            object_id=instance.pk,
            changes={
                'status': {
                    'old': old_status,
                    'new': instance.status,
                }
            }
        )

        return Response(
            {"message": "Academic Department activated successfully."},
            status=status.HTTP_200_OK
        )


    @action(detail=False, methods=["get"], url_path="options")
    def get_options(self, request):
        status_param = request.query_params.get("status", "").strip().lower()
        if status_param == "active":
            base_qs = AcademicDepartment.objects.filter(status__iexact="active")
        elif status_param == "inactive":
            base_qs = AcademicDepartment.objects.exclude(status__iexact="active")
        else:
            base_qs = AcademicDepartment.objects.all()

        stream_filter = request.query_params.get("stream", "").strip()
        type_filter = request.query_params.get("type", "").strip()
        category_filter = request.query_params.get("category", "").strip()
        degree_filter = request.query_params.get("degree", "").strip()
        branch_filter = request.query_params.get("branch", "").strip()

        # All records for frontend client-side dynamic filtering
        records = [
            {
                "stream": (r.get("stream") or "").strip(),
                "type": (r.get("type") or "").strip(),
                "category": (r.get("category") or "").strip(),
                "degree": (r.get("degree") or "").strip(),
                "branch": (r.get("branch") or "").strip(),
                "code": (r.get("code") or "").strip(),
                "status": (r.get("status") or "").strip().lower(),
            }
            for r in base_qs.values("stream", "type", "category", "degree", "branch", "code", "status").distinct()
        ]

        model_streams = [choice[0] for choice in AcademicDepartment.STREAM_CHOICES]
        db_streams = [x.strip() for x in base_qs.exclude(stream="").values_list("stream", flat=True).distinct() if x.strip()]
        streams = sorted(list(set(model_streams) | set(db_streams)))

        model_types = [choice[0] for choice in AcademicDepartment.TYPE_CHOICES]
        type_qs = base_qs.exclude(type="")
        if stream_filter and stream_filter.upper() != "ALL":
            type_qs = type_qs.filter(stream__iexact=stream_filter)
        db_types = [x.strip() for x in type_qs.values_list("type", flat=True).distinct() if x.strip()]
        types = sorted(list(set(model_types) | set(db_types))) if not stream_filter else (db_types or model_types)

        model_categories = [choice[0] for choice in AcademicDepartment.CATEGORY_CHOICES]
        cat_qs = base_qs.exclude(category="")
        if stream_filter and stream_filter.upper() != "ALL":
            cat_qs = cat_qs.filter(stream__iexact=stream_filter)
        if type_filter and type_filter.upper() != "ALL":
            cat_qs = cat_qs.filter(type__iexact=type_filter)
        db_categories = [x.strip() for x in cat_qs.values_list("category", flat=True).distinct() if x.strip()]
        categories = sorted(list(set(model_categories) | set(db_categories))) if not (stream_filter or type_filter) else (db_categories or model_categories)

        deg_qs = base_qs.exclude(degree="")
        if stream_filter and stream_filter.upper() != "ALL":
            deg_qs = deg_qs.filter(stream__iexact=stream_filter)
        if type_filter and type_filter.upper() != "ALL":
            deg_qs = deg_qs.filter(type__iexact=type_filter)
        if category_filter and category_filter.upper() != "ALL":
            deg_qs = deg_qs.filter(category__iexact=category_filter)
        degrees = sorted(list(set([x.strip() for x in deg_qs.values_list("degree", flat=True).distinct() if x.strip()])))

        branch_qs = base_qs.exclude(branch="")
        if stream_filter and stream_filter.upper() != "ALL":
            branch_qs = branch_qs.filter(stream__iexact=stream_filter)
        if type_filter and type_filter.upper() != "ALL":
            branch_qs = branch_qs.filter(type__iexact=type_filter)
        if category_filter and category_filter.upper() != "ALL":
            branch_qs = branch_qs.filter(category__iexact=category_filter)
        if degree_filter and degree_filter.upper() != "ALL":
            branch_qs = branch_qs.filter(degree__iexact=degree_filter)
        branches = sorted(list(set([x.strip() for x in branch_qs.values_list("branch", flat=True).distinct() if x.strip()])))

        code_qs = base_qs.exclude(code="")
        if stream_filter and stream_filter.upper() != "ALL":
            code_qs = code_qs.filter(stream__iexact=stream_filter)
        if type_filter and type_filter.upper() != "ALL":
            code_qs = code_qs.filter(type__iexact=type_filter)
        if category_filter and category_filter.upper() != "ALL":
            code_qs = code_qs.filter(category__iexact=category_filter)
        if degree_filter and degree_filter.upper() != "ALL":
            code_qs = code_qs.filter(degree__iexact=degree_filter)
        if branch_filter and branch_filter.upper() != "ALL":
            code_qs = code_qs.filter(branch__iexact=branch_filter)
        codes = sorted(list(set([x.strip() for x in code_qs.values_list("code", flat=True).distinct() if x.strip()])))

        return Response({
            "streams": [{"value": x, "label": x} for x in streams if x],
            "types": [{"value": x, "label": x} for x in types if x],
            "categories": [{"value": x, "label": x} for x in categories if x],
            "degrees": [{"value": x, "label": x} for x in degrees if x],
            "branches": [{"value": x, "label": x} for x in branches if x],
            "codes": [{"value": x, "label": x} for x in codes if x],
            "records": records,
        })

    @action(detail=False, methods=['get'], url_path='export')
    def export_excel(self, request):
        qs = self.get_queryset()

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Academic Departments"

        headers = ["Code", "Stream", "Degree", "Branch", "Type", "Category", "Status"]   
        ws.append(headers)
        for dept in qs:
            is_dept_active = str(dept.status or '').strip().lower() == 'active'
            ws.append([
                dept.code,
                dept.stream,
                dept.degree,
                dept.branch,
                dept.type,
                dept.category,
                "Active" if is_dept_active else "Inactive",
            ])

        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=academic_departments.xlsx'
        wb.save(response)

        AuditLog.log(
            request=request,
            action="EXPORT",
            obj=AcademicDepartment,
            object_id="EXPORT_ACADEMIC_DEPARTMENTS",
            object_repr="Exported Academic Departments",
            changes={"exported_count": qs.count()},
        )

        return response

    def _extract_header_map(self, header_row):
        """Map required and optional fields to column indices."""
        REQUIRED_FIELDS = {"code", "stream", "degree", "branch", "type", "category"}
        OPTIONAL_FIELDS = {"status"}

        col_map = {}

        if not header_row:
            return col_map, REQUIRED_FIELDS

        for idx, cell in enumerate(header_row):
            if cell is None:
                continue

            name = str(cell).strip().lower()

            if name in REQUIRED_FIELDS and name not in col_map:
                col_map[name] = idx

            elif name in OPTIONAL_FIELDS and name not in col_map:
                col_map[name] = idx

        missing = REQUIRED_FIELDS - set(col_map.keys())
        return col_map, missing

    @action(detail=False, methods=['post'], url_path='parse_excel', parser_classes=[MultiPartParser, FormParser])
    def parse_excel(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)

        file_name = file.name.lower()

        if not file_name.endswith('.xlsx'):
            return Response(
                {"error": "Unsupported file type. Please upload an .xlsx file."},
                status=status.HTTP_400_BAD_REQUEST
            )
        MAX_FILE_SIZE = 5 * 1024 * 1024

        if file.size > MAX_FILE_SIZE:
            return Response(
                {"error": "File size must be 5 MB or less."},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            wb = openpyxl.load_workbook(
                file,
                read_only=True,
                data_only=True
            )
            ws = wb.active
        except Exception:
            return Response({"error": "Invalid Excel file format"}, status=status.HTTP_400_BAD_REQUEST)

        if ws.max_row < 2:
            wb.close()
            return Response(
                {"error": "File is empty or contains only headers"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            rows = list(ws.iter_rows(values_only=True))
        finally:
            wb.close()

        col_map, missing = self._extract_header_map(rows[0])
        if missing:
            missing_readable = ", ".join(sorted([m.capitalize() for m in missing]))
            return Response({
                "error": f"Missing required header(s): {missing_readable}. Required headers are: Code, Stream, Degree, Branch, Type, Category."
            }, status=status.HTTP_400_BAD_REQUEST)

        db_existing = set(
            AcademicDepartment.objects.values_list('code', 'stream')
        )
        db_existing_lower = {(c.strip().upper(), s.strip().lower()) for c, s in db_existing}

        seen_pairs_in_file = set()
        parsed_rows = []

        summary = {
            "new": 0,
            "invalid": 0,
            "duplicate": 0,
            "already_exists": 0,
            "total": 0
        }

        allowed_streams = {
            choice[0] for choice in AcademicDepartment.STREAM_CHOICES
        }

        for row_idx, row in enumerate(rows[1:], start=2):
            if not any(row):
                continue

            get_val = lambda field: str(row[col_map[field]]).strip() if col_map[field] < len(row) and row[col_map[field]] is not None else ""

            code = get_val("code").upper()
            stream = get_val("stream")
            degree = get_val("degree")
            branch = get_val("branch")
            dept_type = get_val("type")
            category = get_val("category")

            department_status = "active"
            row_errors = []

            if "status" in col_map:
                raw_status = get_val("status")
                if raw_status:
                    status_map = {
                        "active": "active",
                        "inactive": "inactive",
                    }
                    department_status = status_map.get(raw_status.lower())

                    if department_status is None:
                        row_errors.append(
                            f"Invalid Status '{raw_status}'. Allowed values: active, inactive."
                        )

            row_data = {
                "row_number": row_idx,
                "code": code,
                "stream": stream,
                "degree": degree,
                "branch": branch,
                "type": dept_type,
                "category": category,
                "department_status": department_status,
                "status": "NEW",
                "errors": []
            }

            
            if not code:
                row_errors.append("Department Code is required.")
            elif len(code) > 20:
                row_errors.append("Department Code exceeds 20 characters.")

            if not stream:
                row_errors.append("Stream is required.")
            elif not any(
                stream.lower() == allowed_stream.lower()
                for allowed_stream in allowed_streams
            ):
                allowed_values = ", ".join(sorted(allowed_streams))
                row_errors.append(
                    f"Invalid Stream '{stream}'. Allowed values: {allowed_values}."
                )
            else:
                stream = next(s for s in allowed_streams if s.lower() == stream.lower())
                row_data["stream"] = stream
            if not degree:
                row_errors.append("Degree is required.")
            elif len(degree) > 50:
                row_errors.append("Degree exceeds 50 characters.")

            if not branch:
                row_errors.append("Branch is required.")
            elif len(branch) > 100:
                row_errors.append("Branch exceeds 100 characters.")

            if not dept_type:
                row_errors.append("Type is required.")
            elif len(dept_type) > 100:
                row_errors.append("Type exceeds 100 characters.")
            else:
                allowed_types = {
                    choice[0].lower(): choice[0]
                    for choice in AcademicDepartment.TYPE_CHOICES
                }

                matched_type = allowed_types.get(dept_type.lower())

                if matched_type:
                    dept_type = matched_type
                else:
                    row_errors.append(
                        f"Invalid Type '{dept_type}'. Allowed values: UG, PG."
                    )

            if not category:
                row_errors.append("Category is required.")
            elif len(category) > 100:
                row_errors.append("Category exceeds 100 characters.")
            else:
                allowed_categories = {
                    choice[0].lower(): choice[0]
                    for choice in AcademicDepartment.CATEGORY_CHOICES
                }

                matched_category = allowed_categories.get(category.lower())

                if matched_category:
                    category = matched_category
                else:
                    row_errors.append(
                        f"Invalid Category '{category}'. Allowed values: ARTS, SCIENCE."
                    )
            row_data["type"] = dept_type
            row_data["category"] = category 


            summary["total"] += 1

            if row_errors:
                row_data["status"] = "INVALID"
                row_data["errors"] = row_errors
                summary["invalid"] += 1
            else:
                pair = (code, stream.lower())
                if pair in db_existing_lower:
                    row_data["status"] = "ALREADY EXISTS"
                    row_data["errors"] = [f"Department Code '{code}' with Stream '{stream}' already exists in database."]
                    summary["already_exists"] += 1
                elif pair in seen_pairs_in_file:
                    row_data["status"] = "DUPLICATE"
                    row_data["errors"] = [f"Duplicate Department Code '{code}' with Stream '{stream}' in uploaded file."]
                    summary["duplicate"] += 1
                else:
                    seen_pairs_in_file.add(pair)
                    row_data["status"] = "NEW"
                    summary["new"] += 1

            parsed_rows.append(row_data)

        return Response({
            "summary": summary,
            "rows": parsed_rows
        })

    @action(detail=False, methods=['post'], url_path='import', parser_classes=[MultiPartParser, FormParser])
    def import_excel(self, request):
        parse_response = self.parse_excel(request)
        if parse_response.status_code != status.HTTP_200_OK:
            return parse_response

        parsed_data = parse_response.data
        summary = parsed_data.get('summary', {})
        rows = parsed_data.get('rows', [])

        invalid_rows = [r for r in rows if r.get('status') == 'INVALID']
        if invalid_rows:
            details = [
                {
                    "row": r.get('row_number'),
                    "errors": r.get('errors', [])
                }
                for r in invalid_rows
            ]
            return Response(
                {"error": f"Import failed with {len(invalid_rows)} validation error(s)", "details": details},
                status=status.HTTP_400_BAD_REQUEST
            )

        valid_rows = [r for r in rows if r.get('status') == 'NEW']
        if not valid_rows:
            if summary.get('already_exists', 0) > 0 or summary.get('duplicate', 0) > 0:
                return Response(
                    {"message": "Already existing data", "imported_count": 0},
                    status=status.HTTP_200_OK
                )
            return Response(
                {"error": "No valid department records found in file"},
                status=status.HTTP_400_BAD_REQUEST
            )

        items = [
            {
                "code": r["code"],
                "stream": r["stream"],
                "degree": r["degree"],
                "branch": r["branch"],
                "type": r["type"],
                "category": r["category"],
                "department_status": r.get("department_status", "active"),
            }
            for r in valid_rows
        ]

        db_existing = set(
            (c.strip().upper(), s.strip().lower())
            for c, s in AcademicDepartment.objects.values_list('code', 'stream')
        )
        valid_departments = []
        for item in items:
            code = item['code']
            stream = item['stream']
            pair = (code.upper(), stream.lower())
            if pair in db_existing:
                continue
            db_existing.add(pair)
            valid_departments.append(AcademicDepartment(
                code=code,
                stream=stream,
                degree=item['degree'],
                branch=item['branch'],
                type=item['type'],
                category=item['category'],
                status=item['department_status'],
            ))

        with transaction.atomic():
            created_objs = AcademicDepartment.objects.bulk_create(valid_departments)
            AuditLog.log(
                request=request,
                action='IMPORT',
                obj=AcademicDepartment,
                object_id='BULK_IMPORT',
                object_repr='Imported Academic Departments',
                changes={"imported_count": len(created_objs)}
            )

        return Response({
            "message": f"Successfully imported {len(created_objs)} departments",
            "imported_count": len(created_objs)
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='confirm_import')
    def confirm_import(self, request):
        items = request.data.get('items', [])
        if not items or not isinstance(items, list):
            return Response({"error": "No items provided for import"}, status=status.HTTP_400_BAD_REQUEST)

        db_existing = set(
            (c.strip().upper(), s.strip().lower())
            for c, s in AcademicDepartment.objects.values_list('code', 'stream')
        )

        valid_departments = []
        errors = []

        for idx, item in enumerate(items, start=1):
            department_status = str(
                item.get('department_status', 'active')
            ).strip().lower()

            if department_status not in ('active', 'inactive'):
                errors.append({
                    "item": idx,
                    "code": item.get('code'),
                    "errors": {
                        "department_status": [
                            "Invalid status. Allowed values: active, inactive."
                        ]
                    }
                })
                continue
            serializer = AcademicDepartmentSerializer(data=item)
            if not serializer.is_valid():
                errors.append({
                    "item": idx,
                    "code": item.get('code'),
                    "errors": serializer.errors
                })
                continue
           
            code = serializer.validated_data['code']
            stream = serializer.validated_data['stream']
            pair = (code.upper(), stream.lower())

            if pair in db_existing:
                errors.append({"item": idx, "code": code, "errors": f"Department Code '{code}' with Stream '{stream}' already exists."})
                continue

            db_existing.add(pair)
            valid_departments.append(AcademicDepartment(
                code=code,
                stream=stream,
                degree=serializer.validated_data['degree'],
                branch=serializer.validated_data['branch'],
                type=serializer.validated_data['type'],
                category=serializer.validated_data['category'],
                status=department_status,
            ))

        if errors and not valid_departments:
            return Response({"error": "Validation failed for all items", "details": errors}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            created_objs = AcademicDepartment.objects.bulk_create(valid_departments)
            AuditLog.log(
                request=request,
                action='IMPORT',
                obj=AcademicDepartment,
                object_id='BULK_IMPORT',
                object_repr='Imported Academic Departments',
                changes={"imported_count": len(created_objs)}
            )

        return Response({
            "message": f"Successfully imported {len(created_objs)} departments",
            "imported_count": len(created_objs)
        }, status=status.HTTP_201_CREATED)

    