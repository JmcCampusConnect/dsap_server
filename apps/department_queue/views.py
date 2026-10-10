"""
Department Queue — Views

Implements the staff-facing service request queue management API.

Endpoint summary:
  GET    /api/department-queue/                         List requests for user's dept/role
  GET    /api/department-queue/{id}/                    Full request detail
  PATCH  /api/department-queue/{id}/documents/{doc_id}/ Verify / reject a document
  POST   /api/department-queue/{id}/forward/            Forward to next workflow step
  POST   /api/department-queue/{id}/return/             Return to student for correction
  POST   /api/department-queue/{id}/approve/            Final approval
  POST   /api/department-queue/{id}/reject/             Reject the request
  POST   /api/department-queue/{id}/complete/           Mark as completed/issued
  GET    /api/department-queue/{id}/history/            Chronological workflow history
"""
import logging

from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.accounts.role_constants import Roles
from apps.documents.models import Document
from apps.requests.models import Request
from apps.services.models import ServiceDocument
from apps.workflow.constants import AllowedActions, NotificationEventCodes, RequestStatuses
from apps.workflow.models import WorkflowHistory, WorkflowStep
from common.pagination import StandardPagination

from .notification_service import send_workflow_notification
from .permissions import IsDeptAdmin, IsDeptQueueUser
from .serializers import (
    DocumentVerifySerializer,
    DeptQueueDetailSerializer,
    DeptQueueListSerializer,
    QueueWorkflowHistorySerializer,
    WorkflowActionSerializer,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Status → allowed action transitions
# ---------------------------------------------------------------------------
# Maps the current request status to which actions are permissible.
# The workflow step's own `allowed_actions` list provides a second layer of
# validation — BOTH constraints must be satisfied before an action proceeds.

_TRANSITION_RULES = {
    # action           : set of request statuses from which the action is valid
    AllowedActions.FORWARD:  {RequestStatuses.SUBMITTED, RequestStatuses.UNDER_VERIFICATION},
    AllowedActions.RETURN:   {RequestStatuses.SUBMITTED, RequestStatuses.UNDER_VERIFICATION},
    AllowedActions.APPROVE:  {RequestStatuses.SUBMITTED, RequestStatuses.UNDER_VERIFICATION, RequestStatuses.APPROVED},
    AllowedActions.REJECT:   {RequestStatuses.SUBMITTED, RequestStatuses.UNDER_VERIFICATION},
    AllowedActions.COMPLETE: {RequestStatuses.APPROVED},
}

# Status that each action produces
_ACTION_TO_STATUS = {
    AllowedActions.FORWARD:  RequestStatuses.UNDER_VERIFICATION,
    AllowedActions.RETURN:   RequestStatuses.RETURNED,
    AllowedActions.APPROVE:  RequestStatuses.APPROVED,
    AllowedActions.REJECT:   RequestStatuses.REJECTED,
    AllowedActions.COMPLETE: RequestStatuses.COMPLETED,
}


class DeptQueueViewSet(GenericViewSet):
    """
    Staff-facing ViewSet for the department service request queue.
    """

    permission_classes = [IsAuthenticated, IsDeptQueueUser]
    pagination_class = StandardPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        'request_number',
        'student_id__name',
        'student_id__register_number',
    ]
    ordering_fields = ['submitted_at', 'updated_at', 'request_number', 'current_status']
    ordering = ['-updated_at']

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_user_dept_id(self):
        """Return the authenticated user's service department id, or None."""
        user = self.request.user
        dept = getattr(user, 'service_department_id', None)
        return getattr(dept, 'id', None) if dept else None

    def _is_system_admin(self):
        return self.request.user.is_system_admin()

    def _build_base_queryset(self):
        """
        Returns the scoped queryset for the current user.
        - SYSTEM_ADMIN: all non-DRAFT requests across departments.
        - SERVICE_DEPT_STAFF: requests in their department whose current step
          is appropriate for their role (responsible_role == SERVICE_DEPT_STAFF).
        - SERVICE_DEPT_ADMIN: requests in their department whose current step
          is a department step (SERVICE_DEPT_ADMIN or SERVICE_DEPT_STAFF).
        """
        user = self.request.user
        qs = (
            Request.objects
            .exclude(current_status=RequestStatuses.DRAFT)
            .select_related(
                'student_id',
                'student_id__academic_department_id',
                'service_id',
                'service_id__service_department_id',
                'current_step_id',
                'current_step_id__responsible_role_id',
            )
        )
        if not self._is_system_admin():
            dept_id = self._get_user_dept_id()
            if not dept_id:
                return Request.objects.none()
            qs = qs.filter(service_id__service_department_id=dept_id)
            if user.role_name == Roles.SERVICE_DEPT_STAFF:
                qs = qs.filter(current_step_id__responsible_role_id=user.role_id)
            elif user.role_name == Roles.SERVICE_DEPT_ADMIN:
                qs = qs.filter(
                    current_step_id__responsible_role_id__name__in=[
                        Roles.SERVICE_DEPT_ADMIN,
                        Roles.SERVICE_DEPT_STAFF,
                    ]
                )
        return qs

    def _get_request_or_403(self, pk):
        """
        Return the Request with the given pk if authorized.
        Raises 404 if the request does not exist in the database or is DRAFT.
        Raises 403 Forbidden if the request belongs to another department.
        """
        try:
            req = Request.objects.select_related(
                'student_id',
                'student_id__academic_department_id',
                'service_id',
                'service_id__service_department_id',
                'current_step_id',
                'current_step_id__responsible_role_id',
            ).get(pk=pk)
        except Request.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound({'detail': 'Request not found.'})

        if req.current_status == RequestStatuses.DRAFT:
            from rest_framework.exceptions import NotFound
            raise NotFound({'detail': 'Draft requests are not accessible in the department queue.'})

        if not self._is_system_admin():
            user_dept_id = self._get_user_dept_id()
            if not user_dept_id or req.service_id.service_department_id_id != user_dept_id:
                raise PermissionDenied({'detail': 'You do not have permission to access requests outside your department.'})

        return req

    def _assert_step_permission(self, request_obj, action_code):
        """
        Validate that:
        1. The current user's role matches the step's responsible_role (unless SYSTEM_ADMIN).
        2. The request is in a state from which the action is allowed.
        3. The current step's allowed_actions includes action_code (or equivalent for forward).

        Raises PermissionDenied (403) or ValidationError (400) on failure.
        """
        step = request_obj.current_step_id
        if not step:
            raise ValidationError({'detail': 'Request has no current workflow step.'})

        # 1. Role check (SYSTEM_ADMIN bypasses)
        if not self._is_system_admin():
            user = self.request.user
            step_role = getattr(step.responsible_role_id, 'name', None)
            user_role = user.role_name
            if step_role != user_role:
                raise PermissionDenied(
                    f"You do not have permission to perform '{action_code}' on this step. "
                    f"Step requires role '{step_role}'; your role is '{user_role}'."
                )

        # 2. State check
        valid_statuses = _TRANSITION_RULES.get(action_code, set())
        if request_obj.current_status not in valid_statuses:
            raise ValidationError({
                'detail': (
                    f"Action '{action_code}' is not permitted when the request is "
                    f"in '{request_obj.current_status}' status. "
                    f"Valid statuses: {sorted(valid_statuses)}."
                )
            })

        # 3. Allowed-actions check on the step
        if action_code == AllowedActions.FORWARD:
            step_allows = (
                AllowedActions.FORWARD in step.allowed_actions
                or AllowedActions.APPROVE in step.allowed_actions
            )
        elif action_code == AllowedActions.COMPLETE:
            step_allows = True
        else:
            step_allows = action_code in step.allowed_actions

        if not step_allows:
            raise ValidationError({
                'detail': (
                    f"Action '{action_code}' is not in the allowed actions for the "
                    f"current workflow step '{step.step_name}'. "
                    f"Allowed: {step.allowed_actions}."
                )
            })

    def _assert_admin_action(self, action_label):
        """Raise PermissionDenied if the user is not a dept admin or system admin."""
        user = self.request.user
        if not user.has_any_role([Roles.SERVICE_DEPT_ADMIN, Roles.SYSTEM_ADMIN]):
            raise PermissionDenied(
                f"Only SERVICE_DEPT_ADMIN or SYSTEM_ADMIN can perform '{action_label}'."
            )

    def _record_history(self, request_obj, step, action_code, remarks):
        """Create a WorkflowHistory record for the current transition."""
        WorkflowHistory.objects.create(
            request_id=request_obj,
            step_id=step,
            action_by_user_id=self.request.user,
            action=action_code,
            remarks=remarks or '',
        )

    # ------------------------------------------------------------------
    # GET /api/department-queue/
    # ------------------------------------------------------------------

    def list(self, request):
        """
        Return requests for the user's department (paginated).
        Query params:
          - status: filter by current_status
          - service: filter by service_id
          - search: search by request_number, student name, register number
        """
        qs = self._build_base_queryset()

        # Status filter
        status_param = request.query_params.get('status', '').strip().upper()
        if status_param and status_param != 'ALL':
            qs = qs.filter(current_status=status_param)

        # Service filter
        service_param = request.query_params.get('service', '').strip()
        if service_param and service_param.isdigit():
            qs = qs.filter(service_id=int(service_param))

        # Apply DRF search and ordering filters
        for backend in self.filter_backends:
            qs = backend().filter_queryset(request, qs, self)

        # Build service-level summary (counts by service and status)
        summary = self._build_service_summary(qs)

        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = DeptQueueListSerializer(page, many=True)
            paginated = self.get_paginated_response(serializer.data)
            paginated.data['summary'] = summary
            return paginated

        serializer = DeptQueueListSerializer(qs, many=True)
        return Response({'results': serializer.data, 'summary': summary})

    def _build_service_summary(self, qs):
        """
        Return a list of service-level groups with total and per-status counts.
        Uses the same queryset that backs the listing so filters are respected.
        """
        rows = (
            qs.values(
                'service_id',
                'service_id__name',
                'service_id__code',
                'current_status',
            )
            .annotate(count=Count('id'))
            .order_by('service_id', 'current_status')
        )

        services: dict = {}
        for row in rows:
            sid = row['service_id']
            if sid not in services:
                services[sid] = {
                    'service_id': sid,
                    'service_name': row['service_id__name'],
                    'service_code': row['service_id__code'],
                    'total': 0,
                    'by_status': {},
                }
            services[sid]['total'] += row['count']
            services[sid]['by_status'][row['current_status']] = row['count']

        return list(services.values())

    # ------------------------------------------------------------------
    # GET /api/department-queue/{id}/
    # ------------------------------------------------------------------

    def retrieve(self, request, pk=None):
        request_obj = self._get_request_or_403(pk)
        serializer = DeptQueueDetailSerializer(request_obj)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # ------------------------------------------------------------------
    # PATCH /api/department-queue/{id}/documents/{doc_id}/
    # ------------------------------------------------------------------

    @action(detail=True, methods=['patch'], url_path=r'documents/(?P<doc_id>[0-9]+)')
    def verify_document(self, request, pk=None, doc_id=None):
        """Verify or reject a specific document belonging to this request."""
        request_obj = self._get_request_or_403(pk)

        # Request must be in an actionable state for doc verification
        if request_obj.current_status not in (
            RequestStatuses.SUBMITTED, RequestStatuses.UNDER_VERIFICATION
        ):
            return Response(
                {'detail': 'Documents can only be reviewed for requests that are submitted or under verification.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Fetch document — enforce it belongs to this request (prevents URL manipulation)
        try:
            document = Document.objects.get(pk=doc_id, request_id=request_obj)
        except Document.DoesNotExist:
            return Response(
                {'detail': 'Document not found for this request.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = DocumentVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_status = serializer.validated_data['verification_status']
        remarks = serializer.validated_data.get('rejection_remarks', None)

        # Validate status transition
        if document.verification_status == new_status:
            return Response(
                {'detail': f'Document is already {new_status}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if document.verification_status == 'VERIFIED' and new_status == 'REJECTED':
            return Response(
                {'detail': 'A verified document cannot be rejected. Return the request first.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        document.verification_status = new_status
        if new_status == 'REJECTED':
            document.rejection_remarks = remarks
        else:
            document.rejection_remarks = None
        document.save(update_fields=['verification_status', 'rejection_remarks', 'updated_at'])

        from .serializers import QueueDocumentSerializer
        return Response(QueueDocumentSerializer(document).data, status=status.HTTP_200_OK)

    # ------------------------------------------------------------------
    # POST /api/department-queue/{id}/forward/
    # ------------------------------------------------------------------

    @action(detail=True, methods=['post'], url_path='forward')
    def forward(self, request, pk=None):
        """
        Forward the request to the next workflow step.
        Requires all mandatory documents to be VERIFIED.
        """
        request_obj = self._get_request_or_403(pk)
        self._assert_step_permission(request_obj, AllowedActions.FORWARD)

        # Validate: all mandatory documents must be VERIFIED
        service = request_obj.service_id
        mandatory_doc_ids = set(
            ServiceDocument.objects
            .filter(service_id=service, is_mandatory=True)
            .values_list('id', flat=True)
        )
        if mandatory_doc_ids:
            verified_doc_ids = set(
                Document.objects
                .filter(
                    request_id=request_obj,
                    service_document_id_id__in=mandatory_doc_ids,
                    verification_status='VERIFIED',
                )
                .values_list('service_document_id_id', flat=True)
            )
            unverified_ids = mandatory_doc_ids - verified_doc_ids
            if unverified_ids:
                unverified_names = list(
                    ServiceDocument.objects
                    .filter(id__in=unverified_ids)
                    .values_list('document_name', flat=True)
                )
                raise ValidationError({
                    'detail': 'All mandatory documents must be verified before forwarding.',
                    'unverified_documents': unverified_names,
                })

        # Find the next workflow step
        current_step = request_obj.current_step_id
        next_step = (
            WorkflowStep.objects
            .filter(
                service_id=service,
                step_order__gt=current_step.step_order,
            )
            .order_by('step_order')
            .first()
        )

        if not next_step:
            raise ValidationError({
                'detail': 'No next workflow step found. Use approve or complete instead.'
            })

        serializer = WorkflowActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        remarks = serializer.validated_data.get('remarks', '')

        with transaction.atomic():
            request_obj.current_step_id = next_step
            request_obj.current_status = _ACTION_TO_STATUS[AllowedActions.FORWARD]
            request_obj.save(update_fields=['current_step_id', 'current_status', 'updated_at'])
            self._record_history(request_obj, current_step, AllowedActions.FORWARD, remarks)
            send_workflow_notification(request_obj, AllowedActions.FORWARD)

        return Response(
            DeptQueueDetailSerializer(request_obj).data,
            status=status.HTTP_200_OK,
        )

    # ------------------------------------------------------------------
    # POST /api/department-queue/{id}/return/
    # ------------------------------------------------------------------

    @action(detail=True, methods=['post'], url_path='return')
    def return_request(self, request, pk=None):
        """Return the request to the student for correction. Remarks are required."""
        request_obj = self._get_request_or_403(pk)
        self._assert_step_permission(request_obj, AllowedActions.RETURN)

        serializer = WorkflowActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        remarks = (serializer.validated_data.get('remarks') or '').strip()

        if not remarks:
            raise ValidationError({'remarks': 'Remarks are required when returning a request.'})

        current_step = request_obj.current_step_id

        with transaction.atomic():
            request_obj.current_status = _ACTION_TO_STATUS[AllowedActions.RETURN]
            # Keep current_step_id so when student resubmits it lands in the right step
            request_obj.save(update_fields=['current_status', 'updated_at'])
            self._record_history(request_obj, current_step, AllowedActions.RETURN, remarks)
            send_workflow_notification(request_obj, AllowedActions.RETURN)

        return Response(
            DeptQueueDetailSerializer(request_obj).data,
            status=status.HTTP_200_OK,
        )

    # ------------------------------------------------------------------
    # POST /api/department-queue/{id}/approve/
    # ------------------------------------------------------------------

    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, pk=None):
        """Final approval. Restricted to SERVICE_DEPT_ADMIN and SYSTEM_ADMIN."""
        request_obj = self._get_request_or_403(pk)
        self._assert_admin_action('approve')
        self._assert_step_permission(request_obj, AllowedActions.APPROVE)

        serializer = WorkflowActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        remarks = serializer.validated_data.get('remarks', '')

        current_step = request_obj.current_step_id

        with transaction.atomic():
            request_obj.current_status = _ACTION_TO_STATUS[AllowedActions.APPROVE]
            request_obj.save(update_fields=['current_status', 'updated_at'])
            self._record_history(request_obj, current_step, AllowedActions.APPROVE, remarks)
            send_workflow_notification(request_obj, AllowedActions.APPROVE)

        return Response(
            DeptQueueDetailSerializer(request_obj).data,
            status=status.HTTP_200_OK,
        )

    # ------------------------------------------------------------------
    # POST /api/department-queue/{id}/reject/
    # ------------------------------------------------------------------

    @action(detail=True, methods=['post'], url_path='reject')
    def reject(self, request, pk=None):
        """Reject the request. Restricted to SERVICE_DEPT_ADMIN and SYSTEM_ADMIN. Remarks required."""
        request_obj = self._get_request_or_403(pk)
        self._assert_admin_action('reject')
        self._assert_step_permission(request_obj, AllowedActions.REJECT)

        serializer = WorkflowActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        remarks = (serializer.validated_data.get('remarks') or '').strip()

        if not remarks:
            raise ValidationError({'remarks': 'Remarks are required when rejecting a request.'})

        current_step = request_obj.current_step_id

        with transaction.atomic():
            request_obj.current_status = _ACTION_TO_STATUS[AllowedActions.REJECT]
            request_obj.completed_at = timezone.now()
            request_obj.save(update_fields=['current_status', 'completed_at', 'updated_at'])
            self._record_history(request_obj, current_step, AllowedActions.REJECT, remarks)
            send_workflow_notification(request_obj, AllowedActions.REJECT)

        return Response(
            DeptQueueDetailSerializer(request_obj).data,
            status=status.HTTP_200_OK,
        )

    # ------------------------------------------------------------------
    # POST /api/department-queue/{id}/complete/
    # ------------------------------------------------------------------

    @action(detail=True, methods=['post'], url_path='complete')
    def complete(self, request, pk=None):
        """Mark as completed/issued. Restricted to SERVICE_DEPT_ADMIN and SYSTEM_ADMIN."""
        request_obj = self._get_request_or_403(pk)
        self._assert_admin_action('complete')

        if request_obj.current_status != RequestStatuses.APPROVED:
            raise ValidationError({
                'detail': (
                    f"Only APPROVED requests can be completed. "
                    f"Current status: '{request_obj.current_status}'."
                )
            })

        serializer = WorkflowActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        remarks = serializer.validated_data.get('remarks', '')

        current_step = request_obj.current_step_id

        with transaction.atomic():
            request_obj.current_status = _ACTION_TO_STATUS[AllowedActions.COMPLETE]
            request_obj.completed_at = timezone.now()
            request_obj.save(update_fields=['current_status', 'completed_at', 'updated_at'])
            self._record_history(request_obj, current_step, AllowedActions.COMPLETE, remarks)
            send_workflow_notification(request_obj, AllowedActions.COMPLETE)

        return Response(
            DeptQueueDetailSerializer(request_obj).data,
            status=status.HTTP_200_OK,
        )

    # ------------------------------------------------------------------
    # GET /api/department-queue/{id}/history/
    # ------------------------------------------------------------------

    @action(detail=True, methods=['get'], url_path='history')
    def history(self, request, pk=None):
        """Return chronological workflow history for the request."""
        request_obj = self._get_request_or_403(pk)

        histories = (
            WorkflowHistory.objects
            .filter(request_id=request_obj)
            .select_related(
                'step_id',
                'action_by_user_id',
                'action_by_user_id__role_id',
                'action_by_user_id__student',
            )
            .order_by('action_at')
        )

        serializer = QueueWorkflowHistorySerializer(histories, many=True)
        return Response({
            'request_id': request_obj.id,
            'request_number': request_obj.request_number,
            'current_status': request_obj.current_status,
            'history': serializer.data,
        })
