from django.urls import include, path
from rest_framework.routers import DefaultRouter
from apps.services.views import ServiceViewSet, ServiceFieldViewSet, ServiceDocumentViewSet
from apps.workflow.views import WorkflowStepViewSet

router = DefaultRouter()
router.register(r"", ServiceViewSet, basename="service")
router.register(r"^(?P<service_id>\d+)/documents", ServiceDocumentViewSet, basename="service-documents")

urlpatterns = [
    
    # CRUD for service fields
    path("<int:service_id>/fields/", ServiceFieldViewSet.as_view({'get': 'list', 'post': 'create'})),
    path("<int:service_id>/fields/reorder/", ServiceFieldViewSet.as_view({'patch': 'reorder'})),
    path("<int:service_id>/fields/<int:pk>/", ServiceFieldViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'})),
    
    # Service Directory
    path("service-directory/", ServiceDirectoryViewSet.as_view({'get': 'list_directory'}), name="service-directory-list"),
    path("service-directory/<int:pk>/detail/", ServiceDirectoryViewSet.as_view({'get': 'detail_with_fields'}), name="service-directory-detail"),
    path("service-directory/departments/", ServiceDirectoryViewSet.as_view({'get': 'department_list'}), name="service-directory-departments"),
    path("service-directory/search/", ServiceDirectoryViewSet.as_view({'get': 'search'}), name="service-directory-search"),
    path("service-directory/filter/", ServiceDirectoryViewSet.as_view({'get': 'filter_by_department'}), name="service-directory-filter"),

    # Workflow Steps
    path("<int:service_id>/workflow-steps/", WorkflowStepViewSet.as_view({'get': 'list', 'post': 'create'})),
    path("<int:service_id>/workflow-steps/reorder/", WorkflowStepViewSet.as_view({'patch': 'reorder'})),
    path("<int:service_id>/workflow-steps/options/", WorkflowStepViewSet.as_view({'get': 'options'})),
    path("<int:service_id>/workflow-steps/<int:pk>/", WorkflowStepViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'})),

    path("", include(router.urls)),
]
