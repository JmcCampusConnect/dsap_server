from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.accounts.role_constants import Roles
from apps.audit.models import AuditLog


class AuditLogPermissionAndListTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Roles
        self.admin_role = Role.objects.create(name=Roles.SYSTEM_ADMIN, description="System Admin")
        self.dept_role = Role.objects.create(name=Roles.SERVICE_DEPT_ADMIN, description="Dept Admin")
        self.student_role = Role.objects.create(name=Roles.STUDENT, description="Student")

        # Users
        self.admin_user = User.objects.create(
            username="admin_user",
            email="admin@example.com",
            password_hash="dummy_hash",
            role_id=self.admin_role,
        )
        self.dept_user = User.objects.create(
            username="dept_user",
            email="dept@example.com",
            password_hash="dummy_hash",
            role_id=self.dept_role,
        )
        self.student_user = User.objects.create(
            username="student_user",
            email="student@example.com",
            password_hash="dummy_hash",
            role_id=self.student_role,
        )

        # Audit Logs
        self.log1 = AuditLog.objects.create(
            app_label="accounts",
            model_name="User",
            object_id="101",
            object_repr="User 101",
            action="CREATE",
            changes={"field": "val1"},
            user_id=str(self.admin_user.id),
            user_name=self.admin_user.username,
            ip_address="127.0.0.1",
            user_agent="TestAgent",
            request_path="/api/users/",
        )
        self.log2 = AuditLog.objects.create(
            app_label="accounts",
            model_name="Role",
            object_id="102",
            object_repr="Role 102",
            action="UPDATE",
            changes={"field": "val2"},
            user_id=str(self.dept_user.id),
            user_name=self.dept_user.username,
            ip_address="127.0.0.1",
            user_agent="TestAgent",
            request_path="/api/roles/",
        )
        self.log3 = AuditLog.objects.create(
            app_label="accounts",
            model_name="User",
            object_id="103",
            object_repr="User 103",
            action="DELETE",
            changes={},
            user_id=str(self.admin_user.id),
            user_name=self.admin_user.username,
            ip_address="127.0.0.1",
            user_agent="TestAgent",
            request_path="/api/users/",
        )

    def test_unauthenticated_cannot_access_audit_logs(self):
        endpoints = [
            "/api/audit-logs/",
            "/api/audit-logs/stats/",
            "/api/audit-logs/actions/",
            "/api/audit-logs/models/",
            "/api/audit-logs/export/",
        ]
        for url in endpoints:
            response = self.client.get(url)
            self.assertEqual(
                response.status_code,
                status.HTTP_401_UNAUTHORIZED,
                f"Expected 401 for unauthenticated user on {url}",
            )

    def test_non_admin_cannot_access_audit_logs(self):
        endpoints = [
            "/api/audit-logs/",
            "/api/audit-logs/stats/",
            "/api/audit-logs/actions/",
            "/api/audit-logs/models/",
            "/api/audit-logs/export/",
        ]
        self.client.force_authenticate(user=self.dept_user)
        for url in endpoints:
            response = self.client.get(url)
            self.assertEqual(
                response.status_code,
                status.HTTP_403_FORBIDDEN,
                f"Expected 403 for non-admin user on {url}",
            )

        self.client.force_authenticate(user=self.student_user)
        for url in endpoints:
            response = self.client.get(url)
            self.assertEqual(
                response.status_code,
                status.HTTP_403_FORBIDDEN,
                f"Expected 403 for student user on {url}",
            )

    def test_system_admin_can_access_audit_logs(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/audit-logs/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertEqual(response.data["count"], 3)

    def test_filter_by_action(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/audit-logs/?action=CREATE")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["action"], "CREATE")

    def test_filter_by_action_all_ignored(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/audit-logs/?action=ALL")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)

    def test_filter_by_model_name_and_search(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/audit-logs/?model_name=Role")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

        search_response = self.client.get("/api/audit-logs/?search=Role 102")
        self.assertEqual(search_response.status_code, status.HTTP_200_OK)
        self.assertEqual(search_response.data["count"], 1)

    def test_stats_view(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/audit-logs/stats/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("total"), 3)

    def test_actions_view(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/audit-logs/actions/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        values = [item["value"] for item in response.data]
        self.assertIn("CREATE", values)
        self.assertIn("UPDATE", values)

    def test_models_view(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/audit-logs/models/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertIn("Role", response.data)
        self.assertIn("User", response.data)

    def test_export_view(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/audit-logs/export/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertIn('attachment; filename="audit_logs.xlsx"', response["Content-Disposition"])
