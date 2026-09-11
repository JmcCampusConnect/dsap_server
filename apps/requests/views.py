from django.db.models import Count
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from common.pagination import StandardPagination
from apps.documents.models import Document
from apps.notifications.models import Notification
from apps.requests.models import Request
from apps.workflow.models import WorkflowHistory

from .permissions import IsStudent
from .serializers import (
    MyRequestDetailSerializer,
    MyRequestListSerializer,
    RequestDocumentSerializer,
    RequestNotificationSerializer,
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
