from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import MyRequestViewSet, StudentRequestViewSet

router = DefaultRouter()
router.register(r'my', MyRequestViewSet, basename='my-requests')

request_create = StudentRequestViewSet.as_view({'post': 'create'})
request_detail = StudentRequestViewSet.as_view({'get': 'retrieve', 'put': 'update'})
request_submit = StudentRequestViewSet.as_view({'post': 'submit'})
request_documents = StudentRequestViewSet.as_view({'post': 'upload_document'})
request_document_delete = StudentRequestViewSet.as_view({'delete': 'delete_document'})
request_payment = StudentRequestViewSet.as_view({'get': 'payment'})

urlpatterns = [
    # Explicit submission-flow routes (must precede the router's catch-all)
    path('', request_create, name='request-create'),
    path('<int:pk>/', request_detail, name='request-detail'),
    path('<int:pk>/submit/', request_submit, name='request-submit'),
    path('<int:pk>/documents/', request_documents, name='request-documents'),
    path('<int:pk>/documents/<int:doc_id>/', request_document_delete, name='request-document-delete'),
    path('<int:pk>/payment/', request_payment, name='request-payment'),

    # Existing read-only "my requests" routes
    path('', include(router.urls)),
]