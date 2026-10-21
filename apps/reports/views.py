"""
Reports — Views
Implements the 5 DASP Reporting APIs:
  GET /api/reports/summary/   -> KPI aggregations and status breakdown
  GET /api/reports/requests/  -> Paginated, filterable tabular request records
  GET /api/reports/revenue/   -> Revenue breakdown by service & payment method
  GET /api/reports/export/    -> Synchronous Excel/CSV streaming download
  GET /api/reports/options/   -> Pre-scoped dynamic filter dropdown choices
"""
from django.db.models import Count, Sum
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.departments.models import AcademicDepartment, ServiceDepartment
from apps.payments.models import Payment
from apps.reports.permissions import IsReportViewer
from apps.reports.serializers import (
    AcademicDepartmentMiniSerializer,
    RequestReportSerializer,
    ServiceDepartmentMiniSerializer,
    ServiceOptionSerializer,
)
from apps.reports.services import (
    REQUEST_EXPORT_COLUMNS,
    REVENUE_EXPORT_COLUMNS,
    apply_request_filters,
    calculate_revenue_report,
    generate_csv_export,
    generate_excel_export,
    generate_requests_data_rows,
    get_scoped_request_queryset,
    log_report_export,
    parse_date_param,
)
from apps.services.models import Service
from apps.students.models import Student
from apps.workflow.constants import RequestStatuses
from common.pagination import StandardPagination


class ReportSummaryView(APIView):
    """
    Returns aggregate headline numbers, status breakdown, and revenue summary.
    """

    permission_classes = [IsAuthenticated, IsReportViewer]

    def get(self, request):
        user = request.user
        params = request.query_params

        # Base query scoped by user role
        base_qs = get_scoped_request_queryset(user)
        filtered_qs = apply_request_filters(base_qs, params, user)

        # 1. Total Requests
        total_requests = filtered_qs.count()

        # 2. Status Counts (ensuring all 6 submission statuses are initialized)
        status_counts = {
            RequestStatuses.SUBMITTED: 0,
            RequestStatuses.UNDER_VERIFICATION: 0,
            RequestStatuses.APPROVED: 0,
            RequestStatuses.COMPLETED: 0,
            RequestStatuses.REJECTED: 0,
            RequestStatuses.RETURNED: 0,
        }
        status_rows = (
            filtered_qs.order_by().values('current_status')
            .annotate(cnt=Count('id'))
        )
        for row in status_rows:
            st = row['current_status']
            if st in status_counts:
                status_counts[st] = row['cnt']

        # 3. Revenue Summary (linked to filtered requests)
        payments = Payment.objects.filter(request_id__in=filtered_qs)
        succ_payments = payments.filter(payment_status='SUCCESS')
        pend_payments = payments.filter(payment_status='PENDING')

        total_collected = succ_payments.aggregate(s=Sum('amount'))['s'] or 0
        successful_transactions = succ_payments.count()
        pending_amount = pend_payments.aggregate(s=Sum('amount'))['s'] or 0

        # 4. Resolve Names for filters_applied
        dept_id = params.get('service_department_id')
        service_id = params.get('service_id')
        acad_dept_id = params.get('academic_department_id')

        dept_name = None
        if dept_id and str(dept_id).isdigit():
            dept_obj = ServiceDepartment.objects.filter(pk=int(dept_id)).first()
            if dept_obj:
                dept_name = dept_obj.name

        service_name = None
        if service_id and str(service_id).isdigit():
            svc_obj = Service.objects.filter(pk=int(service_id)).first()
            if svc_obj:
                service_name = svc_obj.name

        acad_dept_name = None
        if acad_dept_id and str(acad_dept_id).isdigit():
            acad_obj = AcademicDepartment.objects.filter(pk=int(acad_dept_id)).first()
            if acad_obj:
                acad_dept_name = acad_obj.name

        response_data = {
            "filters_applied": {
                "from_date": params.get('from_date') or None,
                "to_date": params.get('to_date') or None,
                "service_department_id": int(dept_id) if dept_id and str(dept_id).isdigit() else None,
                "service_department_name": dept_name,
                "service_id": int(service_id) if service_id and str(service_id).isdigit() else None,
                "service_name": service_name,
                "academic_department_id": int(acad_dept_id) if acad_dept_id and str(acad_dept_id).isdigit() else None,
                "academic_department_name": acad_dept_name,
                "stream": params.get('stream') or None,
            },
            "total_requests": total_requests,
            "status_counts": status_counts,
            "revenue_summary": {
                "total_collected": f"{total_collected:.2f}",
                "successful_transactions": successful_transactions,
                "pending_amount": f"{pending_amount:.2f}",
            },
        }

        return Response(response_data, status=status.HTTP_200_OK)


class RequestReportListView(generics.ListAPIView):
    """
    Paginated, searchable, and sortable tabular list of service request records.
    """

    permission_classes = [IsAuthenticated, IsReportViewer]
    pagination_class = StandardPagination
    serializer_class = RequestReportSerializer

    def get_queryset(self):
        user = self.request.user
        base_qs = get_scoped_request_queryset(user)
        return apply_request_filters(base_qs, self.request.query_params, user)


class RevenueReportView(APIView):
    """
    Financial breakdown of revenue collected from successful payments.
    Filtered by payment completion date (paid_at).
    """

    permission_classes = [IsAuthenticated, IsReportViewer]

    def get(self, request):
        user = request.user
        data = calculate_revenue_report(user, request.query_params)
        return Response(data, status=status.HTTP_200_OK)


class ExportReportView(APIView):
    """
    Direct synchronous Excel (.xlsx) and CSV file download endpoint.
    Automatically logs an EXPORT event in AuditLog.
    """

    permission_classes = [IsAuthenticated, IsReportViewer]

    def perform_content_negotiation(self, request, force=False):
        # Prevent DRF's ?format= parameter from triggering 404 when looking for a DRF renderer
        renderers = self.get_renderers()
        return (renderers[0], renderers[0].media_type)

    def get(self, request):
        params = request.query_params
        report_type = params.get('report_type', 'requests').strip().lower()
        export_format = params.get('format', 'xlsx').strip().lower()

        # Validate parameters
        if report_type not in ['requests', 'revenue']:
            raise ValidationError({
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "One or more query parameters are invalid.",
                    "details": {
                        "report_type": ["Must be either 'requests' or 'revenue'."]
                    }
                }
            })

        if export_format not in ['xlsx', 'csv']:
            raise ValidationError({
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "One or more query parameters are invalid.",
                    "details": {
                        "format": [f"Unsupported export format '{export_format}'. Supported formats: 'xlsx', 'csv'."]
                    }
                }
            })

        # Generate data according to report type
        if report_type == 'requests':
            base_qs = get_scoped_request_queryset(request.user)
            filtered_qs = apply_request_filters(base_qs, params, request.user)
            headers = REQUEST_EXPORT_COLUMNS
            rows = generate_requests_data_rows(filtered_qs)
            filename = f"requests_report_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
        else:  # revenue
            rev_data = calculate_revenue_report(request.user, params)
            headers = REVENUE_EXPORT_COLUMNS
            rows = [
                [
                    item['service_code'],
                    item['service_name'],
                    item['service_department_name'],
                    item['successful_count'],
                    item['total_amount'],
                ]
                for item in rev_data['by_service']
            ]
            filename = f"revenue_report_{timezone.now().strftime('%Y%m%d_%H%M%S')}"

        # Record AuditLog event
        log_report_export(request, report_type, export_format, params.dict())

        # Render response
        if export_format == 'xlsx':
            content = generate_excel_export(headers, rows, sheet_name=report_type.capitalize())
            resp = HttpResponse(
                content,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            resp['Content-Disposition'] = f'attachment; filename="{filename}.xlsx"'
            resp['Content-Length'] = len(content)
            return resp
        else:
            content = generate_csv_export(headers, rows)
            resp = HttpResponse(
                content,
                content_type='text/csv; charset=utf-8'
            )
            resp['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
            resp['Content-Length'] = len(content.encode('utf-8'))
            return resp


class ReportOptionsView(APIView):
    """
    Returns pre-scoped dynamic choices for frontend filter dropdowns.
    """

    permission_classes = [IsAuthenticated, IsReportViewer]

    def get(self, request):
        user = request.user

        # 1. Service Departments
        if user.is_system_admin():
            depts_qs = ServiceDepartment.objects.filter(status__iexact='active').order_by('name')
        else:
            dept_id = getattr(user.service_department_id, 'id', None)
            depts_qs = ServiceDepartment.objects.filter(id=dept_id)

        service_departments = ServiceDepartmentMiniSerializer(depts_qs, many=True).data

        # 2. Services
        if user.is_system_admin():
            services_qs = Service.objects.filter(status=True).order_by('name')
        else:
            dept_id = getattr(user.service_department_id, 'id', None)
            services_qs = Service.objects.filter(service_department_id=dept_id, status=True).order_by('name')

        services = ServiceOptionSerializer(services_qs, many=True).data

        # 3. Academic Departments
        acad_qs = AcademicDepartment.objects.filter(status__iexact='active').order_by('code')
        academic_departments = AcademicDepartmentMiniSerializer(acad_qs, many=True).data

        # 4. Request Statuses (active submission statuses)
        request_statuses = [
            RequestStatuses.SUBMITTED,
            RequestStatuses.UNDER_VERIFICATION,
            RequestStatuses.APPROVED,
            RequestStatuses.COMPLETED,
            RequestStatuses.REJECTED,
            RequestStatuses.RETURNED,
        ]

        # 5. Streams
        streams = [
            Student.StreamChoices.SFM.value,
            Student.StreamChoices.SFW.value,
            Student.StreamChoices.AIDED.value,
        ]

        # 6. Payment Statuses
        payment_statuses = [
            'PENDING',
            'SUCCESS',
            'FAILED',
        ]

        return Response({
            "service_departments": service_departments,
            "services": services,
            "academic_departments": academic_departments,
            "request_statuses": request_statuses,
            "streams": streams,
            "payment_statuses": payment_statuses,
        }, status=status.HTTP_200_OK)
