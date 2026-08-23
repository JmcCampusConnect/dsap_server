from django.urls import path
from apps.workflow.views import WorkflowStepViewSet

app_name = "workflow"

urlpatterns = [
    path("options/", WorkflowStepViewSet.as_view({"get": "options"}), name="workflow-options"),
]
