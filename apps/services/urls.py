from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.services.views import ServiceViewSet, ServiceDocumentViewSet

router = DefaultRouter()
router.register(r"", ServiceViewSet, basename="service")
router.register(r"^(?P<service_id>\d+)/documents", ServiceDocumentViewSet, basename="service-documents")

urlpatterns = [
    path("", include(router.urls)),
]
