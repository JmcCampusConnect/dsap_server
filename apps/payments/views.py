from django.utils.dateparse import parse_date
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.accounts.permissions import CanVerifyPayment
from apps.accounts.role_constants import Roles
from apps.requests.models import Request
from apps.workflow.constants import RequestStatuses
from common.pagination import StandardPagination

from .models import Payment, PaymentStatuses
from .serializers import (
    PaymentConfirmSerializer,
    PaymentDetailSerializer,
    PaymentListSerializer,
    PaymentRejectSerializer,
)
from .services import confirm_payment, reject_payment


class PaymentViewSet(GenericViewSet):
    permission_classes = [IsAuthenticated, CanVerifyPayment]
    pagination_class = StandardPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "request_id__request_number",
        "request_id__student_id__name",
        "request_id__student_id__register_number",
    ]
    ordering_fields = ["request_id__submitted_at", "amount", "payment_status"]
    ordering = ["request_id__submitted_at"]

    def get_queryset(self):
        return Payment.objects.select_related(
            "request_id",
            "request_id__student_id",
            "request_id__service_id",
            "request_id__service_id__service_department_id",
            "verified_by",
        ).prefetch_related("verification_history__acted_by")

    def pending(self, request):
        if request.user.role_name == Roles.STUDENT:
            raise PermissionDenied("Students cannot list department payment queues.")

        queryset = self.get_queryset().filter(
            request_id__current_status__in=[
                RequestStatuses.PAYMENT_PENDING,
                RequestStatuses.PAYMENT_ISSUE,
            ],
            payment_status__in=[PaymentStatuses.PENDING, PaymentStatuses.ISSUE],
        )
        if request.user.role_name != Roles.SYSTEM_ADMIN:
            department_id = request.user.service_department_id_id
            if not department_id:
                queryset = queryset.none()
            else:
                queryset = queryset.filter(
                    request_id__service_id__service_department_id_id=department_id
                )

        service_id = request.query_params.get("service")
        if service_id and service_id.isdigit():
            queryset = queryset.filter(request_id__service_id_id=int(service_id))

        status_filter = request.query_params.get("status", "").upper()
        if status_filter in {PaymentStatuses.PENDING, PaymentStatuses.ISSUE}:
            queryset = queryset.filter(payment_status=status_filter)

        submitted_after = request.query_params.get("submitted_after")
        if submitted_after:
            parsed_after = parse_date(submitted_after)
            if not parsed_after:
                raise ValidationError(
                    {"submitted_after": "Use a valid ISO date (YYYY-MM-DD)."}
                )
            queryset = queryset.filter(
                request_id__submitted_at__date__gte=parsed_after
            )
        submitted_before = request.query_params.get("submitted_before")
        if submitted_before:
            parsed_before = parse_date(submitted_before)
            if not parsed_before:
                raise ValidationError(
                    {"submitted_before": "Use a valid ISO date (YYYY-MM-DD)."}
                )
            queryset = queryset.filter(
                request_id__submitted_at__date__lte=parsed_before
            )

        for backend in self.filter_backends:
            queryset = backend().filter_queryset(request, queryset, self)
        page = self.paginate_queryset(queryset)
        if page is not None:
            return self.get_paginated_response(
                PaymentListSerializer(page, many=True).data
            )
        return Response(PaymentListSerializer(queryset, many=True).data)

    def retrieve(self, request, pk=None):
        payment = self.get_object()
        return Response(PaymentDetailSerializer(payment).data)

    @action(detail=True, methods=["post"], url_path="confirm")
    def confirm(self, request, pk=None):
        payment = self.get_object()
        serializer = PaymentConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = confirm_payment(payment, request.user, serializer.validated_data)
        return Response(PaymentDetailSerializer(payment).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        payment = self.get_object()
        serializer = PaymentRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = reject_payment(
            payment,
            request.user,
            serializer.validated_data["reason"],
            serializer.validated_data,
        )
        return Response(PaymentDetailSerializer(payment).data, status=status.HTTP_200_OK)