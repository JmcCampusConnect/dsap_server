from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.accounts.role_constants import Roles


class AuditLogPermissionTests(TestCase):
    endpoints = (
        '/api/audit-logs/',
        '/api/audit-logs/stats/',
        '/api/audit-logs/actions/',
        '/api/audit-logs/models/',
        '/api/audit-logs/export/',
    )

    def setUp(self):
        self.client = APIClient()
        self.student_role = Role.objects.create(
            name=Roles.STUDENT,
            description='Student',
        )
        self.student = User.objects.create(
            username='audit_student',
            email='audit_student@example.com',
            password_hash='hashed-password',
            role_id=self.student_role,
        )
        self.admin_role = Role.objects.create(
            name=Roles.SYSTEM_ADMIN,
            description='System Admin',
        )
        self.admin = User.objects.create(
            username='audit_admin',
            email='audit_admin@example.com',
            password_hash='hashed-password',
            role_id=self.admin_role,
        )

    def test_all_endpoints_reject_anonymous_and_non_admin_users(self):
        for endpoint in self.endpoints:
            with self.subTest(endpoint=endpoint, user='anonymous'):
                response = self.client.get(endpoint)
                self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        self.client.force_authenticate(user=self.student)
        for endpoint in self.endpoints:
            with self.subTest(endpoint=endpoint, user='student'):
                response = self.client.get(endpoint)
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_system_admin_can_access_all_endpoints(self):
        self.client.force_authenticate(user=self.admin)
        for endpoint in self.endpoints:
            with self.subTest(endpoint=endpoint):
                response = self.client.get(endpoint)
                self.assertEqual(response.status_code, status.HTTP_200_OK)
