from rest_framework import serializers
from apps.documents.models import Document
from apps.notifications.models import Notification
from apps.requests.models import Request, RequestFieldValue
from apps.workflow.models import WorkflowHistory
from apps.payments.models import Payment
from apps.services.models import Service

# 1. WRITE / INPUT SERIALIZERS
class RequestCreateSerializer(serializers.Serializer):
    """Input payload for POST /api/requests/ — creates a DRAFT request for a service."""

    service_id = serializers.IntegerField()

    def validate_service_id(self, value):
        try:
            service = Service.objects.get(pk=value)
        except Service.DoesNotExist:
            raise serializers.ValidationError("Service not found.")
        if not service.status:
            raise serializers.ValidationError("Service is not currently available.")
        return value


class RequestFieldValueWriteSerializer(serializers.Serializer):
    """Single field entry inside a request update payload."""

    field_id = serializers.IntegerField()
    field_value = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )


class RequestUpdateSerializer(serializers.Serializer):
    """Input payload for PUT /api/requests/{id}/ — replace-strategy upsert of field values."""

    field_values = RequestFieldValueWriteSerializer(many=True)


class DocumentUploadSerializer(serializers.Serializer):
    """
    Validates a document upload request. Enforces a 10 MB size cap and a small
    allow-list of MIME types to keep storage predictable.
    """

    MAX_FILE_SIZE = 10 * 1024 * 1024
    ALLOWED_CONTENT_TYPES = {
        'application/pdf',
        'image/jpeg',
        'image/png',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    }

    service_document_id = serializers.IntegerField()
    file = serializers.FileField()

    def validate_file(self, value):
        if value.size > self.MAX_FILE_SIZE:
            raise serializers.ValidationError("File size exceeds the 10 MB limit.")
        content_type = getattr(value, 'content_type', None)
        if content_type and content_type not in self.ALLOWED_CONTENT_TYPES:
            raise serializers.ValidationError(f"Unsupported file type: {content_type}")
        return value

# 2. READ / MODEL SERIALIZERS
class RequestFieldValueSerializer(serializers.ModelSerializer):
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
            'created_at',
        ]


class RequestDocumentSerializer(serializers.ModelSerializer):
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
            'created_at',
            'updated_at',
        ]

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            'id',
            'request_id',
            'amount',
            'gateway_txn_id',
            'payment_method',
            'payment_status',
            'paid_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

class WorkflowHistorySerializer(serializers.ModelSerializer):
    step_name = serializers.SerializerMethodField()
    step_order = serializers.SerializerMethodField()
    actor_name = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()

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
            'role',
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

    def get_role(self, obj):
        if not obj.action_by_user_id:
            return 'System'
        user = obj.action_by_user_id
        role = getattr(user, 'role_id', None)
        return role.name if role else 'User'


class RequestNotificationSerializer(serializers.ModelSerializer):
    event_code = serializers.CharField(source='template_id.event_code', read_only=True)
    template_body = serializers.CharField(source='template_id.template_body', read_only=True)

    class Meta:
        model = Notification
        fields = [
            'id',
            'channel',
            'event_code',
            'template_body',
            'status',
            'sent_at',
            'created_at',
        ]

# 3. COMPOSITE SERIALIZERS
class MyRequestListSerializer(serializers.ModelSerializer):
    service_id = serializers.IntegerField(source='service_id.id', read_only=True)
    service_name = serializers.CharField(source='service_id.name', read_only=True)
    service_code = serializers.CharField(source='service_id.code', read_only=True)
    department_name = serializers.SerializerMethodField()
    current_step_name = serializers.SerializerMethodField()
    assigned_role = serializers.SerializerMethodField()
    base_fee = serializers.DecimalField(source='service_id.base_fee', max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Request
        fields = [
            'id',
            'request_number',
            'service_id',
            'service_name',
            'service_code',
            'department_name',
            'current_status',
            'current_step_name',
            'assigned_role',
            'base_fee',
            'submitted_at',
            'completed_at',
            'created_at',
            'updated_at',
        ]

    def get_department_name(self, obj):
        svc = getattr(obj, 'service_id', None)
        if svc and getattr(svc, 'service_department_id', None):
            return svc.service_department_id.name
        return None

    def get_current_step_name(self, obj):
        return obj.current_step_id.step_name if obj.current_step_id else None

    def get_assigned_role(self, obj):
        if obj.current_step_id and obj.current_step_id.responsible_role_id:
            return obj.current_step_id.responsible_role_id.name
        return None


class MyRequestDetailSerializer(serializers.ModelSerializer):
    service = serializers.SerializerMethodField()
    current_step = serializers.SerializerMethodField()
    assigned_role = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()
    form_data = serializers.SerializerMethodField()
    documents = serializers.SerializerMethodField()
    timeline = serializers.SerializerMethodField()
    notifications = serializers.SerializerMethodField()
    can_resume_draft = serializers.SerializerMethodField()
    can_resubmit = serializers.SerializerMethodField()

    class Meta:
        model = Request
        fields = [
            'id',
            'request_number',
            'current_status',
            'service',
            'department_name',
            'current_step',
            'assigned_role',
            'submitted_at',
            'completed_at',
            'created_at',
            'updated_at',
            'form_data',
            'documents',
            'timeline',
            'notifications',
            'can_resume_draft',
            'can_resubmit',
        ]

    def get_service(self, obj):
        svc = obj.service_id
        dept = getattr(svc, 'service_department_id', None)
        return {
            'id': svc.id,
            'code': svc.code,
            'name': svc.name,
            'description': svc.description,
            'base_fee': str(svc.base_fee),
            'sla_days': svc.sla_days,
            'department': {
                'id': dept.id if dept else None,
                'code': dept.code if dept else None,
                'name': dept.name if dept else None,
            } if dept else None,
        }

    def get_department_name(self, obj):
        svc = getattr(obj, 'service_id', None)
        if svc and getattr(svc, 'service_department_id', None):
            return svc.service_department_id.name
        return None

    def get_current_step(self, obj):
        if not obj.current_step_id:
            return None
        step = obj.current_step_id
        return {
            'id': step.id,
            'step_order': step.step_order,
            'step_name': step.step_name,
            'action_type': step.action_type,
            'allowed_actions': step.allowed_actions,
            'responsible_role': step.responsible_role_id.name if step.responsible_role_id else None,
        }

    def get_assigned_role(self, obj):
        if obj.current_step_id and obj.current_step_id.responsible_role_id:
            return obj.current_step_id.responsible_role_id.name
        return None

    def get_form_data(self, obj):
        field_values = RequestFieldValue.objects.filter(request_id=obj).select_related('field_id').order_by('field_id__display_order', 'id')
        return RequestFieldValueSerializer(field_values, many=True).data

    def get_documents(self, obj):
        docs = Document.objects.filter(request_id=obj).select_related('service_document_id').order_by('id')
        return RequestDocumentSerializer(docs, many=True).data

    def get_timeline(self, obj):
        histories = WorkflowHistory.objects.filter(request_id=obj).select_related(
            'step_id',
            'action_by_user_id',
            'action_by_user_id__role_id'
        ).order_by('action_at')
        return WorkflowHistorySerializer(histories, many=True).data

    def get_notifications(self, obj):
        notifs = Notification.objects.filter(request_id=obj).select_related('template_id').order_by('created_at')
        return RequestNotificationSerializer(notifs, many=True).data

    def get_can_resume_draft(self, obj):
        return obj.current_status == 'DRAFT'

    def get_can_resubmit(self, obj):
        return obj.current_status == 'RETURNED'
