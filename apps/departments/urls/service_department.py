from django.urls import include, path
from rest_framework.routers import DefaultRouter

from ..views import ServiceDepartmentViewSet

router = DefaultRouter()
router.register(
    r"",
    ServiceDepartmentViewSet,
    basename="service-department",
)

urlpatterns = [
    path("", include(router.urls)),
]