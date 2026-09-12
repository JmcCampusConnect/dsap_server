import hashlib
import uuid
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser, JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from common.pagination import StandardPagination
from apps.documents.models import Document
from apps.notifications.models import Notification
from apps.payments.models import Payment
from apps.requests.models import Request, RequestFieldValue
from apps.services.models import Service, ServiceDocument, ServiceField
from apps.workflow.models import WorkflowHistory, WorkflowStep

from .permissions import IsStudent, IsStudentOwner
from .serializers import (
    DocumentUploadSerializer,
    MyRequestDetailSerializer,
    MyRequestListSerializer,
    PaymentSerializer,
    RequestCreateSerializer,
    RequestDocumentSerializer,
    RequestNotificationSerializer,
    RequestUpdateSerializer,
    WorkflowHistorySerializer,
)


class MyRequestViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Student-facing ViewSet for tracking service requests.
    Strictly enforces that authenticated students can only view their own requests.
    """

    permission_classes = [IsAuthenticated, IsStudent]
    pagination_class = StandardPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        'request_number',
        'service_id__name',
        'service_id__code',
        'service_id__service_department_id__name',
    ]
    ordering_fields = ['created_at', 'submitted_at', 'request_number', 'current_status']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return MyRequestDetailSerializer
        return MyRequestListSerializer

    def get_queryset(self):
        user = self.request.user
        student = getattr(user, 'student', None)
        if not student:
            return Request.objects.none()

        qs = Request.objects.filter(student_id=student).select_related(
            'service_id',
            'service_id__service_department_id',
            'current_step_id',
            'current_step_id__responsible_role_id',
            'student_id',
        )

        status_param = self.request.query_params.get('status')
        if status_param and status_param.strip().upper() != 'ALL':
            qs = qs.filter(current_status__iexact=status_param.strip())

        return qs

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Return status counts for the currently authenticated student.
        """
        student = getattr(request.user, 'student', None)
        if not student:
            return Response(
                {
                    'total': 0,
                    'DRAFT': 0,
                    'SUBMITTED': 0,
                    'UNDER_VERIFICATION': 0,
                    'APPROVED': 0,
                    'COMPLETED': 0,
                    'REJECTED': 0,
                    'RETURNED': 0,
                }
            )

        status_counts = (
            Request.objects.filter(student_id=student)
            .values('current_status')
            .annotate(count=Count('id'))
        )

        counts_dict = {
            'DRAFT': 0,
            'SUBMITTED': 0,
            'UNDER_VERIFICATION': 0,
            'APPROVED': 0,
            'COMPLETED': 0,
            'REJECTED': 0,
            'RETURNED': 0,
        }

        total = 0
        for item in status_counts:
            st = item['current_status'].upper()
            c = item['count']
            total += c
            if st in counts_dict:
                counts_dict[st] = c
            else:
                counts_dict[st] = c

        counts_dict['total'] = total
        return Response(counts_dict, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'])
    def timeline(self, request, pk=None):
        """
        Return workflow history and notifications chronologically for the request.
        Strictly isolated to the student's own requests.
        """
        request_obj = self.get_object()

        histories = (
            WorkflowHistory.objects.filter(request_id=request_obj)
            .select_related(
                'step_id',
                'action_by_user_id',
                'action_by_user_id__role_id',
            )
            .order_by('action_at')
        )
        history_data = WorkflowHistorySerializer(histories, many=True).data

        notifications = (
            Notification.objects.filter(request_id=request_obj)
            .select_related('template_id')
            .order_by('created_at')
        )
        notification_data = RequestNotificationSerializer(notifications, many=True).data

        timeline_items = []
        for h in history_data:
            timeline_items.append({
                'id': f"wf-{h['id']}",
                'type': 'WORKFLOW',
                'action': h['action'],
                'remarks': h['remarks'],
                'step_name': h['step_name'],
                'step_order': h['step_order'],
                'actor_name': h['actor_name'],
                'role': h['role'],
                'timestamp': h['action_at'],
            })

        for n in notification_data:
            timeline_items.append({
                'id': f"notif-{n['id']}",
                'type': 'NOTIFICATION',
                'action': f"Notification: {n['event_code']}",
                'remarks': n['template_body'],
                'step_name': None,
                'step_order': None,
                'actor_name': 'System',
                'role': 'System',
                'timestamp': n['sent_at'] or n['created_at'],
            })

        timeline_items.sort(key=lambda x: str(x['timestamp'] or ''))

        return Response({
            'request_id': request_obj.id,
            'request_number': request_obj.request_number,
            'current_status': request_obj.current_status,
            'current_step': {
                'id': request_obj.current_step_id.id,
                'step_name': request_obj.current_step_id.step_name,
                'step_order': request_obj.current_step_id.step_order,
                'responsible_role': request_obj.current_step_id.responsible_role_id.name
                if request_obj.current_step_id and request_obj.current_step_id.responsible_role_id
                else None,
            }
            if request_obj.current_step_id
            else None,
            'history': history_data,
            'notifications': notification_data,
            'timeline': timeline_items,
        })

    @action(detail=True, methods=['get'])
    def documents(self, request, pk=None):
        """
        Return documents associated with the student's request.
        Strictly isolated to the student's own requests.
        """
        request_obj = self.get_object()
        documents = (
            Document.objects.filter(request_id=request_obj)
            .select_related('service_document_id')
            .order_by('id')
        )
        serializer = RequestDocumentSerializer(documents, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class StudentRequestViewSet(viewsets.GenericViewSet):
    """
    Student-facing write API for the request submission flow.

    Exposes create / update / retrieve / submit / document upload / document
    delete / payment retrieval. All actions are scoped to the authenticated
    student's own requests — cross-student access returns 404.
    """

    permission_classes = [IsAuthenticated, IsStudent, IsStudentOwner]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        student = getattr(self.request.user, 'student', None)
        if not student:
            return Request.objects.none()
        return Request.objects.filter(student_id=student).select_related(
            'service_id',
            'service_id__service_department_id',
            'current_step_id',
            'current_step_id__responsible_role_id',
        )

    def _serialize_detail(self, request_obj):
        return MyRequestDetailSerializer(request_obj, context={'request': self.request}).data

    # ------------------------------------------------------------------
    # POST /api/requests/
    # ------------------------------------------------------------------
    def create(self, request):
        serializer = RequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = Service.objects.select_related('service_department_id').get(
            pk=serializer.validated_data['service_id']
        )
        student = request.user.student
        dept_code = service.service_department_id.code if service.service_department_id else 'REQ'

        with transaction.atomic():
            request_number = Request.generate_request_number(dept_code)

            request_obj = Request.objects.create(
                request_number=request_number,
                student_id=student,
                service_id=service,
                current_status='DRAFT',
            )

            # Seed one empty field-value row per configured service field
            service_fields = list(ServiceField.objects.filter(service_id=service))
            RequestFieldValue.objects.bulk_create([
                RequestFieldValue(
                    request_id=request_obj,
                    field_id=sf,
                    field_value=None,
                )
                for sf in service_fields
            ])

            # Payment record is created immediately with the base fee; status stays PENDING
            Payment.objects.create(
                request_id=request_obj,
                amount=service.base_fee,
                payment_status='PENDING',
            )

        return Response(self._serialize_detail(request_obj), status=status.HTTP_201_CREATED)

    # ------------------------------------------------------------------
    # GET /api/requests/{id}/
    # ------------------------------------------------------------------
    def retrieve(self, request, pk=None):
        request_obj = self.get_object()
        return Response(self._serialize_detail(request_obj), status=status.HTTP_200_OK)

    # ------------------------------------------------------------------
    # PUT /api/requests/{id}/  (draft only)
    # ------------------------------------------------------------------
    def update(self, request, pk=None):
        request_obj = self.get_object()
        if request_obj.current_status != 'DRAFT':
            return Response(
                {'detail': 'Only draft requests can be modified.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = RequestUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        valid_field_ids = set(
            ServiceField.objects
            .filter(service_id=request_obj.service_id)
            .values_list('id', flat=True)
        )

        for item in serializer.validated_data['field_values']:
            fid = item['field_id']
            if fid not in valid_field_ids:
                raise ValidationError({
                    'field_values': f"Field {fid} does not belong to this service."
                })

        with transaction.atomic():
            for item in serializer.validated_data['field_values']:
                RequestFieldValue.objects.update_or_create(
                    request_id=request_obj,
                    field_id_id=item['field_id'],
                    defaults={'field_value': item.get('field_value')},
                )

        request_obj.refresh_from_db()
        return Response(self._serialize_detail(request_obj), status=status.HTTP_200_OK)

    # ------------------------------------------------------------------
    # POST /api/requests/{id}/submit/
    # ------------------------------------------------------------------
    @action(detail=True, methods=['post'], url_path='submit')
    def submit(self, request, pk=None):
        request_obj = self.get_object()
        if request_obj.current_status != 'DRAFT':
            return Response(
                {'detail': 'Only draft requests can be submitted.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        service = request_obj.service_id
        errors = {}

        # 1) All required fields must have a non-empty value
        required_field_ids = set(
            ServiceField.objects
            .filter(service_id=service, is_required=True)
            .values_list('id', flat=True)
        )
        filled_field_ids = set(
            RequestFieldValue.objects
            .filter(request_id=request_obj, field_id_id__in=required_field_ids)
            .exclude(field_value__isnull=True)
            .exclude(field_value='')
            .values_list('field_id_id', flat=True)
        )
        missing_fields = required_field_ids - filled_field_ids
        if missing_fields:
            errors['missing_fields'] = list(
                ServiceField.objects
                .filter(id__in=missing_fields)
                .values_list('field_label', flat=True)
            )

        # 2) All mandatory documents must have at least one upload
        mandatory_doc_ids = set(
            ServiceDocument.objects
            .filter(service_id=service, is_mandatory=True)
            .values_list('id', flat=True)
        )
        uploaded_doc_ids = set(
            Document.objects
            .filter(request_id=request_obj, service_document_id_id__in=mandatory_doc_ids)
            .values_list('service_document_id_id', flat=True)
        )
        missing_docs = mandatory_doc_ids - uploaded_doc_ids
        if missing_docs:
            errors['missing_documents'] = list(
                ServiceDocument.objects
                .filter(id__in=missing_docs)
                .values_list('document_name', flat=True)
            )

        # 3) Payment record must exist (SUCCESS is mocked below until gateway lands)
        payment = Payment.objects.filter(request_id=request_obj).first()
        if not payment:
            errors['payment'] = 'No payment record found for this request.'

        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        first_step = (
            WorkflowStep.objects
            .filter(service_id=service)
            .order_by('step_order', 'id')
            .first()
        )

        now = timezone.now()
        with transaction.atomic():
            # TODO(payment-gateway): remove this block once the real gateway
            # webhook flips payment_status to SUCCESS before submit is allowed.
            if payment.payment_status != 'SUCCESS':
                payment.payment_status = 'SUCCESS'
                payment.paid_at = now
                payment.save()

            request_obj.current_status = 'SUBMITTED'
            request_obj.current_step_id = first_step
            request_obj.submitted_at = now
            request_obj.save()

        return Response(self._serialize_detail(request_obj), status=status.HTTP_200_OK)

    # ------------------------------------------------------------------
    # POST /api/requests/{id}/documents/
    # ------------------------------------------------------------------
    @action(
        detail=True,
        methods=['post'],
        url_path='documents',
        parser_classes=[MultiPartParser, FormParser],
    )
    def upload_document(self, request, pk=None):
        request_obj = self.get_object()
        if request_obj.current_status != 'DRAFT':
            return Response(
                {'detail': 'Documents can only be uploaded to draft requests.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = DocumentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        upload = serializer.validated_data['file']
        service_document_id = serializer.validated_data['service_document_id']

        try:
            service_document = ServiceDocument.objects.get(
                pk=service_document_id,
                service_id=request_obj.service_id,
            )
        except ServiceDocument.DoesNotExist:
            return Response(
                {'service_document_id': 'Checklist item not found for this service.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        content = upload.read()
        file_hash = hashlib.sha256(content).hexdigest()

        extension = Path(upload.name).suffix.lower()
        stored_name = f"requests/{request_obj.id}/{uuid.uuid4().hex}{extension}"
        file_path = default_storage.save(stored_name, ContentFile(content))

        document = Document.objects.create(
            request_id=request_obj,
            service_document_id=service_document,
            file_path=file_path,
            file_hash=file_hash,
            verification_status='PENDING',
        )

        return Response(
            RequestDocumentSerializer(document).data,
            status=status.HTTP_201_CREATED,
        )

    # ------------------------------------------------------------------
    # DELETE /api/requests/{id}/documents/{doc_id}/
    # ------------------------------------------------------------------
    @action(
        detail=True,
        methods=['delete'],
        url_path=r'documents/(?P<doc_id>[0-9]+)',
    )
    def delete_document(self, request, pk=None, doc_id=None):
        request_obj = self.get_object()
        if request_obj.current_status != 'DRAFT':
            return Response(
                {'detail': 'Documents can only be removed from draft requests.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            document = Document.objects.get(pk=doc_id, request_id=request_obj)
        except Document.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        # Remove the physical file; a storage failure must not block the DB cleanup
        if document.file_path:
            try:
                default_storage.delete(document.file_path)
            except Exception:
                pass

        document.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ------------------------------------------------------------------
    # GET /api/requests/{id}/payment/
    # ------------------------------------------------------------------
    @action(detail=True, methods=['get'], url_path='payment')
    def payment(self, request, pk=None):
        request_obj = self.get_object()
        payment = Payment.objects.filter(request_id=request_obj).first()
        if not payment:
            return Response(
                {'detail': 'No payment record for this request.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(PaymentSerializer(payment).data, status=status.HTTP_200_OK)
