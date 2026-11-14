from rest_framework import serializers
from decimal import Decimal

from .models import Payment, PaymentVerificationLog


class PaymentConfirmSerializer(serializers.Serializer):
    amount_received = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01")
    )
    payment_date = serializers.DateField()
    payment_mode = serializers.ChoiceField(choices=Payment.PAYMENT_MODE_CHOICES)
    bank_name = serializers.CharField(max_length=150)
    bank_branch = serializers.CharField(max_length=150, required=False, allow_blank=True)
    receipt_number = serializers.CharField(
        max_length=100, required=False, allow_blank=True
    )
    remarks = serializers.CharField(required=False, allow_blank=True)

    def validate_bank_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Bank name is required.")
        return value


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
            "payment_mode",
            "bank_name",
            "bank_branch",
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
            "department_name",
            "request_status",
            "amount",
            "amount_received",
            "payment_status",
            "payment_date",
            "payment_due_at",
            "submitted_at",
            "created_at",
        ]


class PaymentDetailSerializer(PaymentListSerializer):
    verification_history = PaymentVerificationHistorySerializer(many=True, read_only=True)
    payment_due_date = serializers.DateTimeField(
        source="payment_due_at", read_only=True
    )
    verified_by_name = serializers.CharField(
        source="verified_by.username", read_only=True, allow_null=True
    )

    class Meta(PaymentListSerializer.Meta):
        fields = PaymentListSerializer.Meta.fields + [
            "payment_mode",
            "bank_name",
            "bank_branch",
            "receipt_number",
            "verified_by",
            "verified_by_name",
            "verified_at",
            "remarks",
            "rejection_reason",
            "reminder_count",
            "last_reminder_at",
            "payment_due_date",
            "verification_history",
        ]