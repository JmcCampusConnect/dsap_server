from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from django.shortcuts import get_object_or_404
from django.db import transaction, models

from apps.audit.models import AuditLog
from apps.workflow.models import WorkflowStep, WorkflowHistory
from apps.workflow.serializers import WorkflowStepSerializer, WorkflowHistorySerializer
from apps.workflow.constants import (
    ActionTypes,
    ACTION_TYPE_CHOICES,
    AllowedActions,
    ALLOWED_ACTION_CHOICES,
)
from apps.accounts.models import Role
from apps.services.models import Service


class WorkflowStepViewSet(viewsets.ModelViewSet):
    """
    CRUD for service workflow steps.
    Nested under /api/services/<service_id>/workflow-steps/
    """
    serializer_class = WorkflowStepSerializer
    pagination_class = None

    def get_permissions(self):
        return [AllowAny()]

    def get_queryset(self):
        service_id = self.kwargs.get("service_id")
        if not service_id:
            return WorkflowStep.objects.none()
        return (
            WorkflowStep.objects.filter(service_id=service_id)
            .select_related("responsible_role_id")
            .order_by("step_order", "id")
        )

    def perform_create(self, serializer):
        service_id = self.kwargs.get("service_id")
        service = get_object_or_404(Service, id=service_id)
        
        step_order = serializer.validated_data.get("step_order")
        if not step_order or step_order <= 0:
            last_step = WorkflowStep.objects.filter(service_id=service_id).order_by("-step_order").first()
            step_order = (last_step.step_order + 1) if last_step else 1
            
        instance = serializer.save(service_id=service, step_order=step_order)
        AuditLog.log(
            request=self.request,
            action="CREATE",
            obj=instance,
            object_id=str(instance.id),
            object_repr=str(instance),
            changes=self.get_serializer(instance).data,
        )

    def perform_update(self, serializer):
        service_id = self.kwargs.get("service_id")
        instance = self.get_object()
        if str(instance.service_id_id) != str(service_id):
            return Response(
                {"detail": "Workflow step does not belong to this service."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        old_data = self.get_serializer(instance).data
        updated_instance = serializer.save()
        new_data = self.get_serializer(updated_instance).data
        changes = {}
        for key, new_value in new_data.items():
            old_value = old_data.get(key)
            if old_value != new_value:
                changes[key] = {"old": old_value, "new": new_value}
        AuditLog.log(
            request=self.request,
            action="UPDATE",
            obj=updated_instance,
            object_id=str(updated_instance.id),
            object_repr=str(updated_instance),
            changes=changes,
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        service_id = self.kwargs.get("service_id")
        if str(instance.service_id_id) != str(service_id):
            return Response(
                {"detail": "Workflow step does not belong to this service."},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        object_id = str(instance.id)
        object_repr = str(instance)
        snapshot = self.get_serializer(instance).data
        instance.delete()
        AuditLog.log(
            request=request,
            action="DELETE",
            app_label="workflow",
            model_name="WorkflowStep",
            object_id=object_id,
            object_repr=object_repr,
            changes=snapshot,
        )

        # Re-compact step orders
        with transaction.atomic():
            remaining_steps = WorkflowStep.objects.filter(service_id=service_id).order_by("step_order", "id")
            for idx, step in enumerate(remaining_steps, start=1):
                if step.step_order != idx:
                    step.step_order = idx
                    step.save(update_fields=["step_order"])

        return Response(
            {"detail": "Workflow step deleted successfully."},
            status=status.HTTP_204_NO_CONTENT,
        )

    @action(detail=False, methods=["patch"], url_path="reorder")
    def reorder(self, request, service_id=None):
        """
        Expects a list of objects with { id: <int>, step_order: <int> }
        """
        steps_data = request.data
        if not isinstance(steps_data, list):
            return Response(
                {"detail": "Expected a list of step orders with 'id' and 'step_order'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        service = get_object_or_404(Service, id=service_id)

        with transaction.atomic():
            # Avoid collision during reorder
            WorkflowStep.objects.filter(service_id=service_id).update(
                step_order=models.F("step_order") + 1000
            )

            updated = []
            for item in steps_data:
                step_id = item.get("id")
                new_order = item.get("step_order")
                if step_id is None or new_order is None:
                    continue
                try:
                    step = WorkflowStep.objects.get(id=step_id, service_id=service_id)
                    step.step_order = int(new_order)
                    step.save(update_fields=["step_order"])
                    updated.append(step)
                except (WorkflowStep.DoesNotExist, ValueError):
                    continue

            if updated:
                step_ids_str = ",".join(str(s.id) for s in updated)
                AuditLog.log(
                    request=request,
                    action="UPDATE",
                    app_label="workflow",
                    model_name="WorkflowStep",
                    object_id=step_ids_str,
                    object_repr=f"{service.name} - Reordered Workflow Steps",
                    changes={"reorder": steps_data},
                )

        return Response(
            {"detail": "Workflow steps reordered successfully.", "updated": len(updated)},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="options")
    def options(self, request, service_id=None):
        """
        Returns metadata options for configuring workflow steps.
        """
        roles = Role.objects.all().order_by("name")
        role_options = [
            {
                "value": str(r.id),
                "label": r.description or r.name,
                "name": r.name,
                "id": r.id,
            }
            for r in roles
        ]
        action_type_options = [
            {"value": code, "label": label} for code, label in ACTION_TYPE_CHOICES
        ]
        allowed_action_options = [
            {"value": code, "label": label} for code, label in ALLOWED_ACTION_CHOICES
        ]

        return Response({
            "roles": role_options,
            "action_types": action_type_options,
            "allowed_actions": allowed_action_options,
        })
