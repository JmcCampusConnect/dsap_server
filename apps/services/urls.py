from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.services.views import ServiceViewSet

router = DefaultRouter()
router.register(r"", ServiceViewSet, basename="service")

urlpatterns = [
    path("", include(router.urls)),
]
