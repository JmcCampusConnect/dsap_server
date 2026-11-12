"""
Reports — Serializers
Defines serializers for reporting requests, options, revenue aggregations,
and nested student/service/payment representations.
"""
from rest_framework import serializers

from apps.departments.models import AcademicDepartment, ServiceDepartment
from apps.payments.models import Payment
from apps.requests.models import Request
from apps.services.models import Service
from apps.students.models import Student


# ---------------------------------------------------------------------------
# Nested Mini Serializers for Request Listing
# ---------------------------------------------------------------------------

class AcademicDepartmentMiniSerializer(serializers.ModelSerializer):
    name = serializers.CharField(read_only=True)

    class Meta:
        model = AcademicDepartment
        fields = ['id', 'code', 'name']


class StudentReportSerializer(serializers.ModelSerializer):
    academic_department = AcademicDepartmentMiniSerializer(source='academic_department_id', read_only=True)

    class Meta:
        model = Student
        fields = [
            'id',
            'register_number',
            'name',
            'stream',
            'academic_department',
        ]


class ServiceDepartmentMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceDepartment
        fields = ['id', 'code', 'name']


class ServiceReportSerializer(serializers.ModelSerializer):
    service_department = ServiceDepartmentMiniSerializer(source='service_department_id', read_only=True)

    class Meta:
        model = Service
        fields = [
            'id',
            'code',
            'name',
            'service_department',
        ]


class PaymentReportSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, coerce_to_string=True)

    class Meta:
        model = Payment
        fields = [
            'amount',
            'payment_status',
            'payment_method',
            'gateway_txn_id',
            'paid_at',
        ]


class RequestReportSerializer(serializers.ModelSerializer):
    student = StudentReportSerializer(source='student_id', read_only=True)
    service = ServiceReportSerializer(source='service_id', read_only=True)
    current_step_name = serializers.SerializerMethodField()
    payment = serializers.SerializerMethodField()

    class Meta:
        model = Request
        fields = [
            'id',
            'request_number',
            'student',
            'service',
            'current_status',
            'current_step_name',
            'submitted_at',
            'completed_at',
            'payment',
        ]

    def get_current_step_name(self, obj):
        step = getattr(obj, 'current_step_id', None)
        return step.step_name if step else None

    def get_payment(self, obj):
        payment = getattr(obj, 'payment', None)
        if not payment:
            # Handle reverse relation if not pre-fetched or direct query
            try:
                payment = Payment.objects.filter(request_id=obj).first()
            except Exception:
                payment = None
        if payment:
            return PaymentReportSerializer(payment).data
        return None


# ---------------------------------------------------------------------------
# Options Serializers
# ---------------------------------------------------------------------------

class ServiceOptionSerializer(serializers.ModelSerializer):
    service_department_id = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Service
        fields = ['id', 'code', 'name', 'service_department_id']
