from rest_framework import serializers

from .models import NotificationTemplate


class NotificationTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationTemplate
        fields = ["id", "event_code", "channel", "subject", "template_body"]
        read_only_fields = ["id", "event_code", "channel"]