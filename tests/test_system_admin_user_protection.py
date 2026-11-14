from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.accounts.role_constants import Roles


class SystemAdminUserProtectionTests(TestCase):
    def setUp(self):
        self.roles = {
            role_name: Role.objects.create(name=role_name)
            for role_name in Roles.all()
        }
        self.admin = User.objects.create(
            username="system-admin",
            email="system-admin@example.test",
            password_hash="not-a-real-password",
            role_id=self.roles[Roles.SYSTEM_ADMIN],
            is_active=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def create_target(self, role_name, username="target-user"):
        return User.objects.create(
            username=username,
            email=f"{username}@example.test",
            password_hash="not-a-real-password",
            role_id=self.roles[role_name],
            is_active=True,
        )

    def assert_system_admin_operation_forbidden(self, response):
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.data["detail"],
            "System Admin accounts cannot be edited or deactivated.",
        )

    def test_put_cannot_edit_system_admin(self):
        target = self.create_target(Roles.SYSTEM_ADMIN)

        response = self.client.put(
            f"/api/users/{target.pk}/",
            {
                "username": "renamed-admin",
                "email": target.email,
                "role_id": target.role_id_id,
                "is_active": True,
                "service_department_id": None,
            },
            format="json",
        )

        self.assert_system_admin_operation_forbidden(response)
        target.refresh_from_db()
        self.assertEqual(target.username, "target-user")

    def test_patch_cannot_edit_system_admin(self):
        target = self.create_target(Roles.SYSTEM_ADMIN)

        response = self.client.patch(
            f"/api/users/{target.pk}/",
            {"username": "renamed-admin"},
            format="json",
        )

        self.assert_system_admin_operation_forbidden(response)
        target.refresh_from_db()
        self.assertEqual(target.username, "target-user")

    def test_patch_cannot_deactivate_system_admin(self):
        target = self.create_target(Roles.SYSTEM_ADMIN)

        response = self.client.patch(
            f"/api/users/{target.pk}/",
            {"is_active": False},
            format="json",
        )

        self.assert_system_admin_operation_forbidden(response)
        target.refresh_from_db()
        self.assertTrue(target.is_active)

    def test_delete_cannot_deactivate_system_admin(self):
        target = self.create_target(Roles.SYSTEM_ADMIN)

        response = self.client.delete(f"/api/users/{target.pk}/")

        self.assert_system_admin_operation_forbidden(response)
        target.refresh_from_db()
        self.assertTrue(target.is_active)

    def test_other_managed_roles_can_be_edited_and_deactivated(self):
        for role_name in (Roles.SERVICE_DEPT_ADMIN, Roles.SERVICE_DEPT_STAFF):
            with self.subTest(role=role_name):
                target = self.create_target(
                    role_name,
                    username=f"{role_name.lower()}-target",
                )

                edit_response = self.client.patch(
                    f"/api/users/{target.pk}/",
                    {"username": f"{role_name.lower()}-renamed"},
                    format="json",
                )
                self.assertEqual(edit_response.status_code, 200)

                deactivate_response = self.client.delete(
                    f"/api/users/{target.pk}/"
                )
                self.assertEqual(deactivate_response.status_code, 204)

                target.refresh_from_db()
                self.assertEqual(target.username, f"{role_name.lower()}-renamed")
                self.assertFalse(target.is_active)
