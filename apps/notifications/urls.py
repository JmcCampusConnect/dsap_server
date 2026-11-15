from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import NotificationHistoryViewSet, NotificationTemplateViewSet

router = DefaultRouter()
router.register("templates", NotificationTemplateViewSet, basename="notification-template")
router.register("history", NotificationHistoryViewSet, basename="notification-history")

urlpatterns = [
    path("", include(router.urls)),
]
