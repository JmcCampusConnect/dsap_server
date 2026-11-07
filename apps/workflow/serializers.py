from rest_framework import serializers
from apps.workflow.models import WorkflowStep, WorkflowHistory
from apps.accounts.models import Role
from apps.accounts.role_constants import Roles
from apps.workflow.constants import ActionTypes, AllowedActions, configure_role_action


class RoleRefSerializer(serializers.ModelSerializer):
    """Lightweight nested representation of Role."""
    class Meta:
        model = Role
        fields = ["id", "name", "description"]


class WorkflowStepSerializer(serializers.ModelSerializer):
    """
    Serializer for configuring generic workflow steps for a service.
    """
    responsible_role = RoleRefSerializer(source="responsible_role_id", read_only=True)
    responsible_role_id = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.filter(name__in=Roles.all()),
        write_only=False,
    )

    class Meta:
        model = WorkflowStep
        fields = [
            "id",
            "service_id",
            "step_order",
            "step_name",
            "responsible_role_id",
            "responsible_role",
            "action_type",
            "allowed_actions",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "service_id", "created_at", "updated_at"]

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        # Ensure responsible_role_id is integer ID in output for frontend dropdown binding
        if instance.responsible_role_id_id is not None:
            ret["responsible_role_id"] = instance.responsible_role_id_id
        return ret

    def validate_step_name(self, value):
        if not value or not str(value).strip():
            raise serializers.ValidationError("Step name cannot be empty.")
        return str(value).strip()

    def validate_action_type(self, value):
        if not value:
            raise serializers.ValidationError("Action type is required.")
        val_upper = str(value).strip().upper()
        if val_upper not in ActionTypes.all():
            raise serializers.ValidationError(
                f"Invalid action type '{value}'. Allowed: {ActionTypes.all()}"
            )
        return val_upper

    def validate_allowed_actions(self, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("allowed_actions must be a list of action codes.")
        
        valid_actions = AllowedActions.all()
        normalized = []
        for act in value:
            if not isinstance(act, str):
                continue
            act_upper = act.strip().upper()
            if act_upper in valid_actions and act_upper not in normalized:
                normalized.append(act_upper)
            elif act_upper not in valid_actions:
                raise serializers.ValidationError(
                    f"Invalid action '{act}'. Allowed actions are: {valid_actions}"
                )
        return normalized

    def validate(self, attrs):
        role = attrs.get(
            "responsible_role_id",
            self.instance.responsible_role_id if self.instance else None,
        )
        actions = attrs.get(
            "allowed_actions",
            self.instance.allowed_actions if self.instance else [],
        )
        if role:
            step_order = attrs.get(
                "step_order",
                self.instance.step_order if self.instance else None,
            )
            step_name = attrs.get(
                "step_name",
                self.instance.step_name if self.instance else None,
            )
            attrs["allowed_actions"] = configure_role_action(
                role.name,
                actions,
                step_name=step_name,
                step_order=step_order,
            )
        return attrs


class WorkflowHistorySerializer(serializers.ModelSerializer):
    """
    Serializer for workflow transition logs and audit history.
    """
    action_by_username = serializers.CharField(source="action_by_user_id.username", read_only=True)
    step_name = serializers.CharField(source="step_id.step_name", read_only=True, default=None)

    class Meta:
        model = WorkflowHistory
        fields = [
            "id",
            "request_id",
            "step_id",
            "step_name",
            "action_by_user_id",
            "action_by_username",
            "action",
            "remarks",
            "action_at",
        ]
        read_only_fields = ["id", "action_at"]
