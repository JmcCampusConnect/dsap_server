"""
Views for Notification Templates and Notification History.
Protected with IsAuthenticated and IsSystemAdmin permissions.
Audit logging integrated for all administrative modifications.
"""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsSystemAdmin
from apps.audit.models import AuditLog
from common.pagination import StandardPagination

from .models import Notification, NotificationStatuses, NotificationTemplate
from .serializers import (
    NotificationHistoryDetailSerializer,
    NotificationHistorySerializer,
    NotificationTemplatePreviewSerializer,
    NotificationTemplateSerializer,
    NotificationTemplateTestSendSerializer,
)
from .services import (
    SUPPORTED_PLACEHOLDERS,
    dispatch_notification,
    get_sample_context,
    preview_template,
    retry_notification,
)
from apps.workflow.constants import NotificationEventCodes


class NotificationTemplateViewSet(viewsets.ModelViewSet):
    """
    CRUD and actions for administrator-managed notification templates.
    Strictly protected for SYSTEM_ADMIN role.
    """

    queryset = NotificationTemplate.objects.all().order_by("event_code", "channel", "id")
    serializer_class = NotificationTemplateSerializer
    permission_classes = [IsAuthenticated, IsSystemAdmin]
    pagination_class = StandardPagination
    search_fields = ["name", "subject", "event_code"]
    ordering_fields = ["name", "event_code", "channel", "is_active", "updated_at"]
    ordering = ["event_code", "channel", "id"]

    def get_queryset(self):
        qs = super().get_queryset()
        channel = self.request.query_params.get("channel")
        event_code = self.request.query_params.get("event_code")
        is_active = self.request.query_params.get("is_active")

        if channel and channel.upper() != "ALL":
            qs = qs.filter(channel__iexact=channel.strip())
        if event_code and event_code.upper() != "ALL":
            qs = qs.filter(event_code__iexact=event_code.strip())
        if is_active is not None and is_active != "":
            active_bool = is_active.lower() in ("true", "1", "t")
            qs = qs.filter(is_active=active_bool)
        return qs

    @action(detail=False, methods=["get"], url_path="options")
    def options(self, request):
        templates = NotificationTemplate.objects.all()
        return Response(
            {
                "total_count": templates.count(),
                "channels": list(
                    templates.order_by()
                    .values_list("channel", flat=True)
                    .distinct()
                    .order_by("channel")
                ),
                "email_event_codes": list(
                    templates.filter(channel="EMAIL")
                    .order_by()
                    .values_list("event_code", flat=True)
                    .distinct()
                    .order_by("event_code")
                ),
            }
        )

    def perform_create(self, serializer):
        instance = serializer.save()
        AuditLog.log(
            request=self.request,
            action="CREATE",
            obj=instance,
            object_repr=f"NotificationTemplate {instance.event_code} ({instance.channel})",
            changes={
                "name": instance.name,
                "event_code": instance.event_code,
                "channel": instance.channel,
                "subject": instance.subject,
                "is_active": instance.is_active,
            },
        )

    def perform_update(self, serializer):
        old_instance = self.get_object()
        old_values = {
            "name": old_instance.name,
            "subject": old_instance.subject,
            "template_body": old_instance.template_body,
            "is_active": old_instance.is_active,
        }
        instance = serializer.save()
        new_values = {
            "name": instance.name,
            "subject": instance.subject,
            "template_body": instance.template_body,
            "is_active": instance.is_active,
        }
        diff = {
            k: {"old": old_values[k], "new": new_values[k]}
            for k in old_values
            if old_values[k] != new_values[k]
        }
        AuditLog.log(
            request=self.request,
            action="UPDATE",
            obj=instance,
            object_repr=f"NotificationTemplate {instance.event_code} ({instance.channel})",
            changes=diff,
        )

    def destroy(self, request, *args, **kwargs):
        raise MethodNotAllowed(
            "DELETE",
            detail="Templates with notification history cannot be deleted. Deactivate the template instead.",
        )

    @action(detail=False, methods=["get"], url_path="placeholders")
    def placeholders(self, request):
        """List all supported template placeholders, descriptions, and sample data."""
        data = [
            {
                "key": key,
                "token": f"{{{key}}}",
                "description": info["description"],
                "sample": info["sample"],
                "required": info["required"],
            }
            for key, info in SUPPORTED_PLACEHOLDERS.items()
        ]
        return Response(
            {
                "placeholders": data,
                "sample_context": get_sample_context(),
                "supported_events": list(NotificationEventCodes.supported()),
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="preview")
    def preview(self, request, pk=None):
        """Preview rendered subject, HTML, and text using sample data or optional custom context."""
        template = self.get_object()
        serializer = NotificationTemplatePreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        custom_context = serializer.validated_data.get("context", {})
        subject = serializer.validated_data.get("subject", template.subject)
        body = serializer.validated_data.get("template_body", template.template_body)

        try:
            rendered = preview_template(
                subject_template=subject,
                body_template=body,
                custom_context=custom_context,
            )
            return Response(rendered, status=status.HTTP_200_OK)
        except DjangoValidationError as exc:
            raise ValidationError(detail=str(exc))

    @action(detail=True, methods=["post"], url_path="send-test")
    def send_test(self, request, pk=None):
        """Send a test email for this template to an authorized recipient."""
        template = self.get_object()
        serializer = NotificationTemplateTestSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        recipient_email = serializer.validated_data["recipient_email"]
        custom_context = serializer.validated_data.get("context", {})
        admin_email = (request.user.email or "").strip().casefold()
        if not admin_email:
            raise ValidationError(
                {"recipient_email": "Add a registered email address to your admin account before testing."}
            )
        if recipient_email.strip().casefold() != admin_email:
            raise ValidationError(
                {"recipient_email": "Test emails may only be sent to your registered admin email address."}
            )

        notif = dispatch_notification(
            event_code=template.event_code,
            is_test=True,
            test_recipient_email=recipient_email,
            admin_user=request.user,
            extra_context=custom_context,
        )

        if not notif:
            return Response(
                {"detail": "Failed to create test notification record."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        AuditLog.log(
            request=request,
            action="UPDATE",
            obj=template,
            object_repr=f"Test Email: {template.event_code} -> {recipient_email}",
            changes={
                "action": "SEND_TEST_EMAIL",
                "recipient_email": recipient_email,
                "status": notif.status,
                "success": notif.status == NotificationStatuses.SENT,
            },
        )

        return Response(
            {
                "notification_id": notif.id,
                "status": notif.status,
                "recipient_email": notif.recipient_email,
                "provider_message_id": notif.provider_message_id,
                "delivery_error": notif.delivery_error,
                "sent_at": notif.sent_at,
            },
            status=status.HTTP_200_OK if notif.status == NotificationStatuses.SENT else status.HTTP_502_BAD_GATEWAY,
        )

    @action(detail=True, methods=["post"], url_path="toggle-active")
    def toggle_active(self, request, pk=None):
        """Toggle active / inactive state of a notification template."""
        template = self.get_object()
        old_val = template.is_active
        template.is_active = not old_val
        template.save(update_fields=["is_active", "updated_at"])

        AuditLog.log(
            request=request,
            action="ACTIVATE" if template.is_active else "DEACTIVATE",
            obj=template,
            object_repr=f"NotificationTemplate {template.event_code} ({template.channel})",
            changes={"is_active": {"old": old_val, "new": template.is_active}},
        )

        return Response(
            NotificationTemplateSerializer(template).data,
            status=status.HTTP_200_OK,
        )


class NotificationHistoryViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    Paginated notification history, delivery tracking, and manual retry.
    Strictly protected for SYSTEM_ADMIN role.
    """

    queryset = (
        Notification.objects.select_related("request_id", "user_id", "template_id")
        .all()
        .order_by("-created_at", "-id")
    )
    permission_classes = [IsAuthenticated, IsSystemAdmin]
    pagination_class = StandardPagination
    ordering_fields = ["created_at", "status", "channel", "event_code", "recipient_email"]
    ordering = ["-created_at", "-id"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return NotificationHistoryDetailSerializer
        return NotificationHistorySerializer

    def get_queryset(self):
        qs = super().get_queryset()
        status_param = self.request.query_params.get("status")
        channel = self.request.query_params.get("channel")
        event_code = self.request.query_params.get("event_code")
        is_test = self.request.query_params.get("is_test")
        search = self.request.query_params.get("search")

        if status_param and status_param.upper() != "ALL":
            qs = qs.filter(status__iexact=status_param.strip())
        if channel:
            qs = qs.filter(channel__iexact=channel.strip())
        if event_code:
            qs = qs.filter(event_code__iexact=event_code.strip())
        if is_test is not None and is_test != "":
            test_bool = is_test.lower() in ("true", "1", "t")
            qs = qs.filter(is_test=test_bool)
        if search:
            search = search.strip()
            qs = qs.filter(
                Q(recipient_email__icontains=search)
                | Q(subject__icontains=search)
                | Q(request_number_snapshot__icontains=search)
                | Q(request_id__request_number__icontains=search)
            )

        return qs

    @action(detail=True, methods=["post"], url_path="retry")
    def retry(self, request, pk=None):
        """Retry sending an eligible failed notification."""
        try:
            updated_notif = retry_notification(notification_id=pk, admin_user=request.user)
            return Response(
                NotificationHistoryDetailSerializer(updated_notif).data,
                status=status.HTTP_200_OK,
            )
        except DjangoValidationError as exc:
            raise ValidationError(detail=str(exc))
