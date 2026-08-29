from django.db import models
from django.http import HttpResponse
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from openpyxl import Workbook
from common.pagination import StandardPagination
from .models import AuditLog


class AuditLogListView(ListAPIView):
    
    queryset = AuditLog.objects.all()
    pagination_class = StandardPagination

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        # Filters
        action = request.query_params.get("action")
        model_name = request.query_params.get("model_name")
        user_id = request.query_params.get("user_id")
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        search = request.query_params.get("search")

        if action:
            queryset = queryset.filter(action=action)

        if model_name:
            queryset = queryset.filter(model_name=model_name)

        if user_id:
            queryset = queryset.filter(user_id=user_id)

        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)

        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)

        if search:
            queryset = queryset.filter(
                models.Q(user_name__icontains=search)
                | models.Q(object_repr__icontains=search)
                | models.Q(model_name__icontains=search)
                | models.Q(request_path__icontains=search)
            )

        page = self.paginate_queryset(queryset)

        data = [
            {
                "id": audit_log.id,
                "app_label": audit_log.app_label,
                "model_name": audit_log.model_name,
                "object_id": audit_log.object_id,
                "object_repr": audit_log.object_repr,
                "action": audit_log.action,
                "changes": audit_log.changes,
                "user_id": audit_log.user_id,
                "user_name": audit_log.user_name,
                "ip_address": audit_log.ip_address,
                "user_agent": audit_log.user_agent,
                "request_path": audit_log.request_path,
                "created_at": audit_log.created_at,
            }
            for audit_log in page
        ]

        return self.get_paginated_response(data)


class AuditLogStatsView(ListAPIView):
    def get(self, request, *args, **kwargs):
        total = AuditLog.objects.count()

        return Response({
            "total": total,
        })


class AuditLogActionsView(ListAPIView):
    def get(self, request, *args, **kwargs):
        actions = [
            {
                "value": value,
                "label": label,
            }
            for value, label in AuditLog.ACTION_CHOICES
        ]

        return Response(actions)


class AuditLogModelsView(ListAPIView):
    def get(self, request, *args, **kwargs):
        models = (
            AuditLog.objects
            .exclude(model_name="")
            .exclude(model_name__isnull=True)
            .values_list("model_name", flat=True)
            .distinct()
            .order_by("model_name")
        )

        return Response(list(models))


class AuditLogExportView(ListAPIView):

    def get(self, request, *args, **kwargs):
        queryset = AuditLog.objects.all()
        action = request.query_params.get("action")
        model_name = request.query_params.get("model_name")
        user_id = request.query_params.get("user_id")
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        search = request.query_params.get("search")

        if action:
            queryset = queryset.filter(action=action)

        if model_name:
            queryset = queryset.filter(model_name=model_name)

        if user_id:
            queryset = queryset.filter(user_id=user_id)

        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)

        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)

        if search:
            queryset = queryset.filter(
                models.Q(user_name__icontains=search)
                | models.Q(object_repr__icontains=search)
                | models.Q(model_name__icontains=search)
                | models.Q(request_path__icontains=search)
            )

        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Audit Logs"

        headers = [
            "ID",
            "App Label",
            "Model Name",
            "Object ID",
            "Object",
            "Action",
            "Changes",
            "User ID",
            "User Name",
            "IP Address",
            "User Agent",
            "Request Path",
            "Created At",
        ]

        worksheet.append(headers)

        for audit_log in queryset:
            worksheet.append([
                audit_log.id,
                audit_log.app_label,
                audit_log.model_name,
                audit_log.object_id,
                audit_log.object_repr,
                audit_log.action,
                str(audit_log.changes),
                audit_log.user_id,
                audit_log.user_name,
                audit_log.ip_address,
                audit_log.user_agent,
                audit_log.request_path,
                audit_log.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            ])

        response = HttpResponse(
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            )
        )

        response["Content-Disposition"] = (
            'attachment; filename="audit_logs.xlsx"'
        )

        workbook.save(response)

        return response