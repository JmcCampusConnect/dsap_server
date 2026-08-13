from django.urls import path

from .views import (
    AuditLogListView,
    AuditLogStatsView,
    AuditLogActionsView,
    AuditLogModelsView,
    AuditLogExportView,
)

urlpatterns = [
    path("", AuditLogListView.as_view(), name="audit-log-list"),
    path("stats/", AuditLogStatsView.as_view(), name="audit-log-stats"),
    path("actions/", AuditLogActionsView.as_view(), name="audit-log-actions"),
    path("models/", AuditLogModelsView.as_view(), name="audit-log-models"),
    path("export/", AuditLogExportView.as_view(), name="audit-log-export"),

]
