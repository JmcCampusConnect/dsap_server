from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.accounts.role_constants import Roles
from apps.audit.models import AuditLog
from apps.departments.models import ServiceDepartment
from apps.services.models import Service


class ServiceDeleteIdempotencyTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        admin_role = Role.objects.create(
            name=Roles.SYSTEM_ADMIN,
            description='System Admin',
        )
        admin = User.objects.create(
            username='service_admin',
            email='service_admin@example.com',
            password_hash='hashed-password',
            role_id=admin_role,
        )
        self.client.force_authenticate(user=admin)
        department = ServiceDepartment.objects.create(
            code='SERV',
            name='Services',
        )
        self.service = Service.objects.create(
            code='SVC-1',
            name='Test Service',
            service_department_id=department,
        )

    def test_repeated_delete_keeps_service_deactivated(self):
        url = f'/api/services/{self.service.pk}/'

        first_response = self.client.delete(url)
        second_response = self.client.delete(url)

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        self.service.refresh_from_db()
        self.assertFalse(self.service.status)
        self.assertEqual(
            AuditLog.objects.filter(
                action='DEACTIVATE',
                object_id=str(self.service.pk),
            ).count(),
            1,
        )

    def test_status_can_be_updated_with_patch(self):
        response = self.client.patch(
            f'/api/services/{self.service.pk}/',
            {'status': False},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.service.refresh_from_db()
        self.assertFalse(self.service.status)
