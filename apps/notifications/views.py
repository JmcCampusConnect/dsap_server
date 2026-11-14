from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from apps.accounts.permissions import IsSystemAdmin

from .models import NotificationTemplate
from .serializers import NotificationTemplateSerializer


class NotificationTemplateViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = NotificationTemplate.objects.all().order_by("event_code", "channel")
    serializer_class = NotificationTemplateSerializer
    permission_classes = [IsAuthenticated, IsSystemAdmin]
    http_method_names = ["get", "patch", "head", "options"]