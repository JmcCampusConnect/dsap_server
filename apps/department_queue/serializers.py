"""
Department Queue — Serializers
All serializers are read-only / output-only unless explicitly named as input
serializers (e.g. *WriteSerializer). No model-level writes are done here.
"""
from rest_framework import serializers

from apps.documents.models import Document
from apps.notifications.models import Notification
from apps.requests.models import Request, RequestFieldValue
from apps.students.models import Student
from apps.workflow.models import WorkflowHistory, WorkflowStep
from apps.payments.models import Payment


# ---------------------------------------------------------------------------
# Nested helpers
# ---------------------------------------------------------------------------

class StudentInfoSerializer(serializers.ModelSerializer):
    department_name = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = [
            'id',
            'register_number',
            'name',
            'mobile_number',
            'year_of_admission',
            'section',
            'stream',
            'department_name',
        ]

    def get_department_name(self, obj):
        dept = getattr(obj, 'academic_department_id', None)
        if dept:
            return dept.name
        return None


class QueueDocumentSerializer(serializers.ModelSerializer):
    document_name = serializers.CharField(source='service_document_id.document_name', read_only=True)
    is_mandatory = serializers.BooleanField(source='service_document_id.is_mandatory', read_only=True)

    class Meta:
        model = Document
        fields = [
            'id',
            'service_document_id',
            'document_name',
            'is_mandatory',
            'file_path',
            'file_hash',
            'verification_status',
            'rejection_remarks',
            'created_at',
            'updated_at',
        ]


class QueueFieldValueSerializer(serializers.ModelSerializer):
    field_label = serializers.CharField(source='field_id.field_label', read_only=True)
    field_type = serializers.CharField(source='field_id.field_type', read_only=True)
    display_order = serializers.IntegerField(source='field_id.display_order', read_only=True)

    class Meta:
        model = RequestFieldValue
        fields = [
            'id',
            'field_id',
            'field_label',
            'field_type',
            'field_value',
            'display_order',
        ]


class QueuePaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            'id',
            'amount',
            'payment_status',
            'payment_method',
            'paid_at',
        ]


class QueueWorkflowHistorySerializer(serializers.ModelSerializer):
    step_name = serializers.SerializerMethodField()
    step_order = serializers.SerializerMethodField()
    actor_name = serializers.SerializerMethodField()
    actor_role = serializers.SerializerMethodField()

    class Meta:
        model = WorkflowHistory
        fields = [
            'id',
            'step_id',
            'step_name',
            'step_order',
            'action',
            'remarks',
            'action_at',
            'actor_name',
            'actor_role',
        ]

    def get_step_name(self, obj):
        return obj.step_id.step_name if obj.step_id else None

    def get_step_order(self, obj):
        return obj.step_id.step_order if obj.step_id else None

    def get_actor_name(self, obj):
        if not obj.action_by_user_id:
            return 'System'
        user = obj.action_by_user_id
        if hasattr(user, 'student') and user.student:
            return user.student.name
        return user.username

    def get_actor_role(self, obj):
        if not obj.action_by_user_id:
            return 'System'
        role = getattr(obj.action_by_user_id, 'role_id', None)
        return role.name if role else 'User'


# ---------------------------------------------------------------------------
# Queue list serializer (lightweight — for the queue table)
# ---------------------------------------------------------------------------

class DeptQueueListSerializer(serializers.ModelSerializer):
    """Lightweight listing for the department queue table."""

    service_name = serializers.CharField(source='service_id.name', read_only=True)
    service_code = serializers.CharField(source='service_id.code', read_only=True)
    department_name = serializers.SerializerMethodField()
    student_name = serializers.SerializerMethodField()
    register_number = serializers.SerializerMethodField()
    current_step_name = serializers.SerializerMethodField()
    current_step_order = serializers.SerializerMethodField()
    responsible_role = serializers.SerializerMethodField()
    allowed_actions = serializers.SerializerMethodField()

    class Meta:
        model = Request
        fields = [
            'id',
            'request_number',
            'service_name',
            'service_code',
            'department_name',
            'student_name',
            'register_number',
            'current_status',
            'current_step_name',
            'current_step_order',
            'responsible_role',
            'allowed_actions',
            'submitted_at',
            'updated_at',
        ]

    def get_department_name(self, obj):
        svc = getattr(obj, 'service_id', None)
        if svc and getattr(svc, 'service_department_id', None):
            return svc.service_department_id.name
        return None

    def get_student_name(self, obj):
        student = getattr(obj, 'student_id', None)
        return student.name if student else None

    def get_register_number(self, obj):
        student = getattr(obj, 'student_id', None)
        return student.register_number if student else None

    def get_current_step_name(self, obj):
        return obj.current_step_id.step_name if obj.current_step_id else None

    def get_current_step_order(self, obj):
        return obj.current_step_id.step_order if obj.current_step_id else None

    def get_responsible_role(self, obj):
        if obj.current_step_id and obj.current_step_id.responsible_role_id:
            return obj.current_step_id.responsible_role_id.name
        return None

    def get_allowed_actions(self, obj):
        if obj.current_step_id:
            return obj.current_step_id.allowed_actions
        return []


# ---------------------------------------------------------------------------
# Full detail serializer (for the request detail view)
# ---------------------------------------------------------------------------

class DeptQueueDetailSerializer(serializers.ModelSerializer):
    student = serializers.SerializerMethodField()
    service = serializers.SerializerMethodField()
    department = serializers.SerializerMethodField()
    current_step = serializers.SerializerMethodField()
    form_data = serializers.SerializerMethodField()
    documents = serializers.SerializerMethodField()
    payment = serializers.SerializerMethodField()
    allowed_actions = serializers.SerializerMethodField()

    class Meta:
        model = Request
        fields = [
            'id',
            'request_number',
            'current_status',
            'student',
            'service',
            'department',
            'current_step',
            'allowed_actions',
            'submitted_at',
            'completed_at',
            'created_at',
            'updated_at',
            'form_data',
            'documents',
            'payment',
        ]

    def get_student(self, obj):
        student = getattr(obj, 'student_id', None)
        if not student:
            return None
        return StudentInfoSerializer(student).data

    def get_service(self, obj):
        svc = obj.service_id
        return {
            'id': svc.id,
            'code': svc.code,
            'name': svc.name,
            'description': svc.description,
            'base_fee': str(svc.base_fee),
            'sla_days': svc.sla_days,
        }

    def get_department(self, obj):
        svc = obj.service_id
        dept = getattr(svc, 'service_department_id', None)
        if not dept:
            return None
        return {'id': dept.id, 'code': dept.code, 'name': dept.name}

    def get_current_step(self, obj):
        step = obj.current_step_id
        if not step:
            return None
        return {
            'id': step.id,
            'step_order': step.step_order,
            'step_name': step.step_name,
            'action_type': step.action_type,
            'responsible_role': step.responsible_role_id.name if step.responsible_role_id else None,
            'allowed_actions': step.allowed_actions,
        }

    def get_form_data(self, obj):
        field_values = (
            RequestFieldValue.objects
            .filter(request_id=obj)
            .select_related('field_id')
            .order_by('field_id__display_order', 'id')
        )
        return QueueFieldValueSerializer(field_values, many=True).data

    def get_documents(self, obj):
        docs = (
            Document.objects
            .filter(request_id=obj)
            .select_related('service_document_id')
            .order_by('id')
        )
        return QueueDocumentSerializer(docs, many=True).data

    def get_payment(self, obj):
        payment = Payment.objects.filter(request_id=obj).first()
        if not payment:
            return None
        return QueuePaymentSerializer(payment).data

    def get_allowed_actions(self, obj):
        step = obj.current_step_id
        if step:
            return step.allowed_actions
        return []


# ---------------------------------------------------------------------------
# Input serializers for workflow actions
# ---------------------------------------------------------------------------

class DocumentVerifySerializer(serializers.Serializer):
    """Input for PATCH /department-queue/{id}/documents/{doc_id}/"""

    ALLOWED_STATUSES = ['VERIFIED', 'REJECTED']

    verification_status = serializers.ChoiceField(choices=ALLOWED_STATUSES)
    rejection_remarks = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )

    def validate(self, data):
        if data.get('verification_status') == 'REJECTED':
            remarks = data.get('rejection_remarks', '')
            if not remarks or not str(remarks).strip():
                raise serializers.ValidationError(
                    {'rejection_remarks': 'Rejection remarks are required when rejecting a document.'}
                )
        return data


class WorkflowActionSerializer(serializers.Serializer):
    """Generic input for workflow transition actions (forward/return/approve/reject/complete)."""

    remarks = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )

    def validate_remarks(self, value):
        if value is not None:
            return str(value).strip()
        return value
