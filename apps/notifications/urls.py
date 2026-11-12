from django.urls import path

from .views import NotificationTemplateViewSet

template_list = NotificationTemplateViewSet.as_view({"get": "list"})
template_detail = NotificationTemplateViewSet.as_view(
    {"get": "retrieve", "patch": "partial_update"}
)

urlpatterns = [
    path("templates/", template_list, name="notification-template-list"),
    path("templates/<int:pk>/", template_detail, name="notification-template-detail"),
]
