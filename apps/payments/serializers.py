from rest_framework import serializers
from decimal import Decimal

from .models import Payment, PaymentVerificationLog


class PaymentConfirmSerializer(serializers.Serializer):
    amount_received = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01")
    )
    payment_date = serializers.DateField()
    receipt_number = serializers.CharField(
        max_length=100, required=False, allow_blank=True
    )
    remarks = serializers.CharField(required=False, allow_blank=True)


class PaymentRejectSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=2000)
    remarks = serializers.CharField(required=False, allow_blank=True)

    def validate_reason(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("A rejection reason is required.")
        return value


class PaymentVerificationHistorySerializer(serializers.ModelSerializer):
    staff_name = serializers.CharField(source="acted_by.username", read_only=True)

    class Meta:
        model = PaymentVerificationLog
        fields = [
            "id",
            "action",
            "amount_received",
            "payment_date",
            "receipt_number",
            "remarks",
            "reason",
            "acted_by",
            "staff_name",
            "acted_at",
        ]


class PaymentListSerializer(serializers.ModelSerializer):
    request_number = serializers.CharField(
        source="request_id.request_number", read_only=True
    )
    student_name = serializers.CharField(
        source="request_id.student_id.name", read_only=True
    )
    register_number = serializers.CharField(
        source="request_id.student_id.register_number", read_only=True
    )
    service_name = serializers.CharField(
        source="request_id.service_id.name", read_only=True
    )
    service_code = serializers.CharField(
        source="request_id.service_id.code", read_only=True
    )
    service_id = serializers.IntegerField(
        source="request_id.service_id_id", read_only=True
    )
    department_name = serializers.CharField(
        source="request_id.service_id.service_department_id.name", read_only=True
    )
    submitted_at = serializers.DateTimeField(
        source="request_id.submitted_at", read_only=True
    )
    request_status = serializers.CharField(
        source="request_id.current_status", read_only=True
    )

    class Meta:
        model = Payment
        fields = [
            "id",
            "request_id",
            "request_number",
            "student_name",
            "register_number",
            "service_id",
            "service_name",
            "service_code",
            "department_name",
            "request_status",
            "amount",
            "amount_received",
            "payment_status",
            "payment_date",
            "submitted_at",
            "created_at",
        ]


class PaymentDetailSerializer(PaymentListSerializer):
    verification_history = PaymentVerificationHistorySerializer(many=True, read_only=True)
    current_step_name = serializers.CharField(
        source="request_id.current_step_id.step_name",
        read_only=True,
        allow_null=True,
    )
    verified_by_name = serializers.CharField(
        source="verified_by.username", read_only=True, allow_null=True
    )

    class Meta(PaymentListSerializer.Meta):
        fields = PaymentListSerializer.Meta.fields + [
            "current_step_name",
            "receipt_number",
            "verified_by",
            "verified_by_name",
            "verified_at",
            "remarks",
            "rejection_reason",
            "verification_history",
        ]