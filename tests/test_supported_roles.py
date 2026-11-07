from django.test import TestCase
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate

from apps.accounts.models import Role, User
from apps.accounts.role_constants import Roles
from apps.workflow.views import WorkflowStepViewSet


class SupportedRoleTests(TestCase):
    def setUp(self):
        self.supported_roles = {
            role_name: Role.objects.create(name=role_name)
            for role_name in Roles.all()
        }
        self.supported_role = self.supported_roles[Roles.SYSTEM_ADMIN]
        self.unsupported_role = Role.objects.create(name="UNSUPPORTED_LEGACY_ROLE")
        self.admin = User.objects.create(
            username="role-admin",
            email="role-admin@example.test",
            password_hash="not-a-real-password",
            role_id=self.supported_role,
            is_active=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def test_role_api_does_not_offer_unsupported_legacy_roles(self):
        response = self.client.get("/api/users/roles/")

        self.assertEqual(response.status_code, 200)
        results = (
            response.data["results"]
            if isinstance(response.data, dict)
            else response.data
        )
        role_names = {role["name"] for role in results}

        self.assertEqual(role_names, set(Roles.all()))

    def test_service_options_only_offer_supported_roles(self):
        response = self.client.get("/api/services/options/")

        self.assertEqual(response.status_code, 200)
        role_names = {role["label"] for role in response.data["roles"]}

        self.assertEqual(role_names, set(Roles.all()))

    def test_workflow_options_only_offer_supported_roles(self):
        request = APIRequestFactory().get("/api/services/workflow-steps/options/")
        force_authenticate(request, user=self.admin)

        response = WorkflowStepViewSet.as_view({"get": "options"})(request)

        self.assertEqual(response.status_code, 200)
        role_names = {role["name"] for role in response.data["roles"]}

        self.assertEqual(role_names, set(Roles.all()))

    def test_role_api_rejects_creation_of_unsupported_roles(self):
        role_count = Role.objects.count()
        response = self.client.post(
            "/api/users/roles/",
            {"name": "UNSUPPORTED_LEGACY_ROLE"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Role.objects.count(), role_count)

    def test_unsupported_legacy_role_cannot_be_assigned(self):
        from apps.accounts.serializers.user import UserSerializer

        serializer = UserSerializer(
            data={
                "username": "new-user",
                "email": "new-user@example.test",
                "password": "password",
                "role_id": self.unsupported_role.pk,
            },
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("role_id", serializer.errors)

    def test_student_creation_only_accepts_the_student_role(self):
        from apps.students.serializers import StudentSerializer

        role_queryset = StudentSerializer().fields["role_id"].queryset

        self.assertEqual(
            set(role_queryset.values_list("name", flat=True)),
            {Roles.STUDENT},
        )
