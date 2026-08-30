from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.accounts.role_constants import Roles
from apps.audit.models import AuditLog
from apps.departments.models import AcademicDepartment


class AcademicDepartmentSoftDeleteTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_role = Role.objects.create(name=Roles.SYSTEM_ADMIN, description='System Admin')
        self.admin_user = User.objects.create(
            username='admin_test',
            email='admin@example.com',
            password_hash='hashed_pass',
            role_id=self.admin_role,
        )
        self.client.force_authenticate(user=self.admin_user)

        self.dept_active = AcademicDepartment.objects.create(
            code='MCA',
            stream='SFM',
            degree='M.C.A.',
            branch='Computer Applications',
            type='PG',
            category='SCIENCE',
            status=True,
        )
        self.dept_inactive = AcademicDepartment.objects.create(
            code='OLD',
            stream='SFM',
            degree='B.A.',
            branch='Old Branch',
            type='UG',
            category='ARTS',
            status=False,
        )

    def test_default_status_is_true(self):
        dept = AcademicDepartment.objects.create(
            code='BCA',
            stream='SFM',
            degree='B.C.A.',
            branch='Computer Applications',
            type='UG',
            category='SCIENCE',
        )
        self.assertTrue(dept.status)

    def test_get_queryset_excludes_inactive_departments(self):
        response = self.client.get('/api/academic-departments/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', [])
        codes = [item['code'] for item in results]
        self.assertIn('MCA', codes)
        self.assertNotIn('OLD', codes)

    def test_get_options_excludes_inactive_departments(self):
        response = self.client.get('/api/academic-departments/options/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        records = response.data.get('records', [])
        codes = [r['code'] for r in records]
        self.assertIn('MCA', codes)
        self.assertNotIn('OLD', codes)

    def test_destroy_soft_deletes_department(self):
        response = self.client.delete(f'/api/academic-departments/{self.dept_active.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('message'), 'Academic Department deactivated successfully.')

        # Verify department still exists in database
        self.dept_active.refresh_from_db()
        self.assertFalse(self.dept_active.status)
        self.assertTrue(AcademicDepartment.objects.filter(id=self.dept_active.id).exists())

        # Verify audit log was created
        audit_entry = AuditLog.objects.filter(
            action='DEACTIVATE',
            object_id=str(self.dept_active.pk)
        ).first()
        self.assertIsNotNone(audit_entry)
