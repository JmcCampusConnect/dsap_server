from django.urls import include, path
from rest_framework.routers import DefaultRouter
from apps.services.views import ServiceViewSet, ServiceFieldViewSet, ServiceDocumentViewSet

router = DefaultRouter()
router.register(r"", ServiceViewSet, basename="service")
router.register(r"^(?P<service_id>\d+)/documents", ServiceDocumentViewSet, basename="service-documents")

urlpatterns = [
    path("<int:service_id>/fields/", ServiceFieldViewSet.as_view({'get': 'list', 'post': 'create'})),
    path("<int:service_id>/fields/reorder/", ServiceFieldViewSet.as_view({'patch': 'reorder'})),
    path("<int:service_id>/fields/<int:pk>/", ServiceFieldViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'})),
    path("", include(router.urls)),
]
