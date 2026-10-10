"""Department Queue URL configuration."""
from django.urls import path

from .views import DeptQueueViewSet

queue_list = DeptQueueViewSet.as_view({'get': 'list'})
queue_detail = DeptQueueViewSet.as_view({'get': 'retrieve'})
queue_document_verify = DeptQueueViewSet.as_view({'patch': 'verify_document'})
queue_forward = DeptQueueViewSet.as_view({'post': 'forward'})
queue_return = DeptQueueViewSet.as_view({'post': 'return_request'})
queue_approve = DeptQueueViewSet.as_view({'post': 'approve'})
queue_reject = DeptQueueViewSet.as_view({'post': 'reject'})
queue_complete = DeptQueueViewSet.as_view({'post': 'complete'})
queue_history = DeptQueueViewSet.as_view({'get': 'history'})

urlpatterns = [
    path('', queue_list, name='department-queue-list'),
    path('<int:pk>/', queue_detail, name='department-queue-detail'),
    path('<int:pk>/documents/<int:doc_id>/', queue_document_verify, name='department-queue-document-verify'),
    path('<int:pk>/forward/', queue_forward, name='department-queue-forward'),
    path('<int:pk>/return/', queue_return, name='department-queue-return'),
    path('<int:pk>/approve/', queue_approve, name='department-queue-approve'),
    path('<int:pk>/reject/', queue_reject, name='department-queue-reject'),
    path('<int:pk>/complete/', queue_complete, name='department-queue-complete'),
    path('<int:pk>/history/', queue_history, name='department-queue-history'),
]
