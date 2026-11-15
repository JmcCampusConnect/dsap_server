"""
Serializers for Notification Templates and Notification History.
"""

from rest_framework import serializers

from apps.workflow.constants import NotificationEventCodes

from .models import Notification, NotificationTemplate
from .services import (
    SUPPORTED_PLACEHOLDERS,
    validate_subject,
    validate_template_content,
)


class NotificationTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationTemplate
        fields = [
            "id",
            "name",
            "description",
            "event_code",
            "channel",
            "subject",
            "template_body",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_subject(self, value):
        validate_subject(value)
        return value

    def validate_template_body(self, value):
        from .services import sanitize_html, validate_placeholders
        validate_placeholders(value, field_name="template_body")
        return sanitize_html(value)

    def validate_event_code(self, value):
        if value not in NotificationEventCodes.supported():
            raise serializers.ValidationError("Unsupported notification event code.")
        return value

    def validate(self, attrs):
        if self.instance:
            for field in ("event_code", "channel"):
                if field in attrs and attrs[field] != getattr(self.instance, field):
                    raise serializers.ValidationError(
                        {field: "This field cannot be changed after template creation."}
                    )
        subject = attrs.get("subject", getattr(self.instance, "subject", ""))
        body = attrs.get("template_body", getattr(self.instance, "template_body", ""))
        validate_template_content(subject, body)
        return attrs


class NotificationTemplatePreviewSerializer(serializers.Serializer):
    subject = serializers.CharField(required=False, allow_blank=False, max_length=200)
    template_body = serializers.CharField(required=False, allow_blank=False)
    context = serializers.DictField(
        child=serializers.CharField(allow_blank=True),
        required=False,
        default=dict,
    )

    def validate_context(self, value):
        unknown = set(value) - set(SUPPORTED_PLACEHOLDERS)
        if unknown:
            raise serializers.ValidationError(
                f"Unsupported preview placeholders: {', '.join(sorted(unknown))}."
            )
        return value


class NotificationTemplateTestSendSerializer(serializers.Serializer):
    recipient_email = serializers.EmailField(required=True)
    context = serializers.DictField(
        child=serializers.CharField(allow_blank=True),
        required=False,
        default=dict,
    )

    def validate_context(self, value):
        unknown = set(value) - set(SUPPORTED_PLACEHOLDERS)
        if unknown:
            raise serializers.ValidationError(
                f"Unsupported test placeholders: {', '.join(sorted(unknown))}."
            )
        return value


class NotificationHistorySerializer(serializers.ModelSerializer):
    request_number = serializers.SerializerMethodField()
    template_name = serializers.SerializerMethodField()
    recipient = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "request_id",
            "request_number",
            "user_id",
            "recipient",
            "recipient_email",
            "channel",
            "template_id",
            "template_name",
            "subject",
            "status",
            "delivery_error",
            "retry_count",
            "provider_message_id",
            "event_identifier",
            "event_code",
            "request_number_snapshot",
            "is_test",
            "last_attempt_at",
            "sent_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_request_number(self, obj) -> str:
        if obj.request_id:
            return obj.request_id.request_number
        return obj.request_number_snapshot or ""

    def get_template_name(self, obj) -> str:
        if obj.template_id:
            return obj.template_id.name or obj.template_id.event_code
        return obj.event_code or ""

    def get_recipient(self, obj) -> str:
        return obj.recipient_email or (obj.user_id.username if obj.user_id else "")


class NotificationHistoryDetailSerializer(NotificationHistorySerializer):
    class Meta(NotificationHistorySerializer.Meta):
        fields = NotificationHistorySerializer.Meta.fields + ["message"]
        read_only_fields = fields
