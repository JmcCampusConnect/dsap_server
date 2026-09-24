from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.accounts.role_constants import Roles
from apps.departments.models import ServiceDepartment
from apps.services.models import Service, ServiceField, ServiceDocument
from apps.workflow.models import WorkflowStep


def _get_items(res):
    if isinstance(res.data, list):
        return res.data
    return res.data.get('results', res.data)


class ScopeBasedServiceManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Roles
        cls.role_sysadmin, _ = Role.objects.get_or_create(
            name=Roles.SYSTEM_ADMIN, defaults={'description': 'System Administrator'}
        )
        cls.role_dept_admin, _ = Role.objects.get_or_create(
            name=Roles.SERVICE_DEPT_ADMIN, defaults={'description': 'Department Admin'}
        )
        cls.role_dept_staff, _ = Role.objects.get_or_create(
            name=Roles.SERVICE_DEPT_STAFF, defaults={'description': 'Department Staff'}
        )

        # Service Departments
        cls.dept_a = ServiceDepartment.objects.create(code='DEPT_A', name='Department A')
        cls.dept_b = ServiceDepartment.objects.create(code='DEPT_B', name='Department B')

        # Users
        cls.sysadmin = User.objects.create(
            username='test_sysadmin',
            email='sysadmin@test.edu',
            password_hash='dummy_hash',
            role_id=cls.role_sysadmin,
            service_department_id=None,
        )
        cls.admin_a = User.objects.create(
            username='test_admin_a',
            email='admin_a@test.edu',
            password_hash='dummy_hash',
            role_id=cls.role_dept_admin,
            service_department_id=cls.dept_a,
        )
        cls.staff_a = User.objects.create(
            username='test_staff_a',
            email='staff_a@test.edu',
            password_hash='dummy_hash',
            role_id=cls.role_dept_staff,
            service_department_id=cls.dept_a,
        )
        cls.admin_b = User.objects.create(
            username='test_admin_b',
            email='admin_b@test.edu',
            password_hash='dummy_hash',
            role_id=cls.role_dept_admin,
            service_department_id=cls.dept_b,
        )
        cls.staff_b = User.objects.create(
            username='test_staff_b',
            email='staff_b@test.edu',
            password_hash='dummy_hash',
            role_id=cls.role_dept_staff,
            service_department_id=cls.dept_b,
        )

        # Services
        cls.srv_a1 = Service.objects.create(
            code='SRV-A1',
            name='Service A1',
            service_department_id=cls.dept_a,
            base_fee=100.00,
            sla_days=5,
            status=True,
        )
        cls.srv_a2 = Service.objects.create(
            code='SRV-A2',
            name='Service A2',
            service_department_id=cls.dept_a,
            base_fee=150.00,
            sla_days=10,
            status=False,
        )
        cls.srv_b1 = Service.objects.create(
            code='SRV-B1',
            name='Service B1',
            service_department_id=cls.dept_b,
            base_fee=200.00,
            sla_days=7,
            status=True,
        )

        # Child Resources
        cls.field_a1 = ServiceField.objects.create(
            service_id=cls.srv_a1,
            field_label='Reason A1',
            field_type='TEXT',
            is_required=True,
            display_order=1,
        )
        cls.field_b1 = ServiceField.objects.create(
            service_id=cls.srv_b1,
            field_label='Reason B1',
            field_type='TEXT',
            is_required=True,
            display_order=1,
        )

        cls.doc_a1 = ServiceDocument.objects.create(
            service_id=cls.srv_a1,
            document_name='Doc A1',
            is_mandatory=True,
        )
        cls.doc_b1 = ServiceDocument.objects.create(
            service_id=cls.srv_b1,
            document_name='Doc B1',
            is_mandatory=True,
        )

        cls.step_a1 = WorkflowStep.objects.create(
            service_id=cls.srv_a1,
            step_order=1,
            step_name='Verification A1',
            responsible_role_id=cls.role_dept_admin,
            action_type='APPROVAL',
            allowed_actions=['APPROVE', 'REJECT'],
        )
        cls.step_b1 = WorkflowStep.objects.create(
            service_id=cls.srv_b1,
            step_order=1,
            step_name='Verification B1',
            responsible_role_id=cls.role_dept_admin,
            action_type='APPROVAL',
            allowed_actions=['APPROVE', 'REJECT'],
        )

    def setUp(self):
        self.client = APIClient()

    # ─────────────────────────────────────────────────────────────────────────
    # 1. Service List & Filtering Scoping
    # ─────────────────────────────────────────────────────────────────────────

    def test_sysadmin_can_list_all_services(self):
        self.client.force_authenticate(user=self.sysadmin)
        res = self.client.get('/api/services/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        results = _get_items(res)
        codes = [s['code'] for s in results]
        self.assertIn('SRV-A1', codes)
        self.assertIn('SRV-A2', codes)
        self.assertIn('SRV-B1', codes)

    def test_sysadmin_can_filter_by_department(self):
        self.client.force_authenticate(user=self.sysadmin)
        res = self.client.get(f'/api/services/?service_department_id={self.dept_a.id}')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        results = _get_items(res)
        codes = [s['code'] for s in results]
        self.assertIn('SRV-A1', codes)
        self.assertIn('SRV-A2', codes)
        self.assertNotIn('SRV-B1', codes)

    def test_dept_admin_only_sees_own_department_services(self):
        self.client.force_authenticate(user=self.admin_a)
        res = self.client.get('/api/services/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        results = _get_items(res)
        codes = [s['code'] for s in results]
        self.assertIn('SRV-A1', codes)
        self.assertIn('SRV-A2', codes)
        self.assertNotIn('SRV-B1', codes)

    def test_dept_admin_cannot_tamper_filter_for_foreign_department(self):
        self.client.force_authenticate(user=self.admin_a)
        res = self.client.get(f'/api/services/?service_department_id={self.dept_b.id}')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        results = _get_items(res)
        codes = [s['code'] for s in results]
        self.assertNotIn('SRV-B1', codes)
        for s in results:
            self.assertEqual(s['service_department']['id'], self.dept_a.id)

    def test_dept_staff_only_sees_own_department_services(self):
        self.client.force_authenticate(user=self.staff_a)
        res = self.client.get('/api/services/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        results = _get_items(res)
        codes = [s['code'] for s in results]
        self.assertIn('SRV-A1', codes)
        self.assertIn('SRV-A2', codes)
        self.assertNotIn('SRV-B1', codes)

    # ─────────────────────────────────────────────────────────────────────────
    # 2. Options Scoping
    # ─────────────────────────────────────────────────────────────────────────

    def test_options_scoping(self):
        # Sysadmin gets all departments
        self.client.force_authenticate(user=self.sysadmin)
        res = self.client.get('/api/services/options/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        dept_ids = [d['value'] for d in res.data['departments']]
        self.assertIn(str(self.dept_a.id), dept_ids)
        self.assertIn(str(self.dept_b.id), dept_ids)

        # Admin A gets only Department A
        self.client.force_authenticate(user=self.admin_a)
        res = self.client.get('/api/services/options/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        dept_ids = [d['value'] for d in res.data['departments']]
        self.assertIn(str(self.dept_a.id), dept_ids)
        self.assertNotIn(str(self.dept_b.id), dept_ids)

        # Staff A gets only Department A
        self.client.force_authenticate(user=self.staff_a)
        res = self.client.get('/api/services/options/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        dept_ids = [d['value'] for d in res.data['departments']]
        self.assertIn(str(self.dept_a.id), dept_ids)
        self.assertNotIn(str(self.dept_b.id), dept_ids)

    # ─────────────────────────────────────────────────────────────────────────
    # 3. Service Creation Scoping & Protection
    # ─────────────────────────────────────────────────────────────────────────

    def test_sysadmin_can_create_service_in_any_department(self):
        self.client.force_authenticate(user=self.sysadmin)
        payload = {
            'name': 'New Sysadmin Service',
            'service_department_id': self.dept_b.id,
            'base_fee': 300.00,
            'sla_days': 4,
        }
        res = self.client.post('/api/services/', data=payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        created = Service.objects.get(name='New Sysadmin Service')
        self.assertEqual(created.service_department_id_id, self.dept_b.id)

    def test_dept_admin_create_rejects_foreign_department(self):
        self.client.force_authenticate(user=self.admin_a)
        payload = {
            'name': 'Foreign Dept Attempt',
            'service_department_id': self.dept_b.id,
            'base_fee': 250.00,
            'sla_days': 5,
        }
        res = self.client.post('/api/services/', data=payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_dept_admin_create_binds_to_own_department(self):
        self.client.force_authenticate(user=self.admin_a)
        payload = {
            'name': 'New Admin A Service',
            'service_department_id': self.dept_a.id,
            'base_fee': 250.00,
            'sla_days': 5,
        }
        res = self.client.post('/api/services/', data=payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        created = Service.objects.get(name='New Admin A Service')
        self.assertEqual(created.service_department_id_id, self.dept_a.id)

    def test_dept_staff_cannot_create_service(self):
        self.client.force_authenticate(user=self.staff_a)
        payload = {
            'name': 'Staff Created Service',
            'service_department_id': self.dept_a.id,
            'base_fee': 100.00,
            'sla_days': 5,
        }
        res = self.client.post('/api/services/', data=payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    # ─────────────────────────────────────────────────────────────────────────
    # 4. Service Update & Department Lock
    # ─────────────────────────────────────────────────────────────────────────

    def test_dept_admin_can_update_own_service(self):
        self.client.force_authenticate(user=self.admin_a)
        payload = {
            'name': 'Updated Service A1',
            'service_department_id': self.dept_a.id,
            'base_fee': 120.00,
            'sla_days': 6,
        }
        res = self.client.put(f'/api/services/{self.srv_a1.id}/', data=payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.srv_a1.refresh_from_db()
        self.assertEqual(self.srv_a1.name, 'Updated Service A1')

    def test_dept_admin_cannot_update_foreign_service(self):
        self.client.force_authenticate(user=self.admin_a)
        payload = {
            'name': 'Hacked Service B1',
            'service_department_id': self.dept_b.id,
            'base_fee': 999.00,
            'sla_days': 1,
        }
        res = self.client.put(f'/api/services/{self.srv_b1.id}/', data=payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_dept_admin_cannot_change_department_on_update(self):
        self.client.force_authenticate(user=self.admin_a)
        payload = {
            'name': 'Moved Service A1',
            'service_department_id': self.dept_b.id,
            'base_fee': 100.00,
            'sla_days': 5,
        }
        res = self.client.put(f'/api/services/{self.srv_a1.id}/', data=payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.srv_a1.refresh_from_db()
        self.assertEqual(self.srv_a1.service_department_id_id, self.dept_a.id)

    def test_dept_staff_cannot_update_service(self):
        self.client.force_authenticate(user=self.staff_a)
        payload = {
            'name': 'Staff Modified A1',
            'service_department_id': self.dept_a.id,
            'base_fee': 100.00,
            'sla_days': 5,
        }
        res = self.client.put(f'/api/services/{self.srv_a1.id}/', data=payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    # ─────────────────────────────────────────────────────────────────────────
    # 5. Service Status Toggle (Soft Delete / Destroy)
    # ─────────────────────────────────────────────────────────────────────────

    def test_dept_admin_can_toggle_own_service_status(self):
        self.client.force_authenticate(user=self.admin_a)
        res = self.client.delete(f'/api/services/{self.srv_a1.id}/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.srv_a1.refresh_from_db()
        self.assertFalse(self.srv_a1.status)

    def test_dept_admin_cannot_toggle_foreign_service_status(self):
        self.client.force_authenticate(user=self.admin_a)
        res = self.client.delete(f'/api/services/{self.srv_b1.id}/')
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_dept_staff_cannot_toggle_service_status(self):
        self.client.force_authenticate(user=self.staff_a)
        res = self.client.delete(f'/api/services/{self.srv_a1.id}/')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    # ─────────────────────────────────────────────────────────────────────────
    # 6. ServiceField Scoping
    # ─────────────────────────────────────────────────────────────────────────

    def test_service_field_scoping(self):
        # Admin A can list own service fields
        self.client.force_authenticate(user=self.admin_a)
        res = self.client.get(f'/api/services/{self.srv_a1.id}/fields/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        fields = _get_items(res)
        self.assertEqual(len(fields), 1)

        # Admin A CANNOT list foreign service fields -> 404
        res = self.client.get(f'/api/services/{self.srv_b1.id}/fields/')
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

        # Staff A can read own service fields
        self.client.force_authenticate(user=self.staff_a)
        res = self.client.get(f'/api/services/{self.srv_a1.id}/fields/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        fields = _get_items(res)
        self.assertEqual(len(fields), 1)

        # Staff A CANNOT create a field -> 403
        res = self.client.post(f'/api/services/{self.srv_a1.id}/fields/', data={
            'field_label': 'Staff Field',
            'field_type': 'TEXT',
            'is_required': False,
            'display_order': 2,
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # Admin A can create a field on own service -> 201
        self.client.force_authenticate(user=self.admin_a)
        res = self.client.post(f'/api/services/{self.srv_a1.id}/fields/', data={
            'field_label': 'Admin Field',
            'field_type': 'TEXT',
            'is_required': False,
            'display_order': 2,
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        # Admin A CANNOT create field on foreign service -> 404
        res = self.client.post(f'/api/services/{self.srv_b1.id}/fields/', data={
            'field_label': 'Foreign Field',
            'field_type': 'TEXT',
            'is_required': False,
            'display_order': 2,
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    # ─────────────────────────────────────────────────────────────────────────
    # 7. ServiceDocument Scoping
    # ─────────────────────────────────────────────────────────────────────────

    def test_service_document_scoping(self):
        # Admin A can list own service docs
        self.client.force_authenticate(user=self.admin_a)
        res = self.client.get(f'/api/services/{self.srv_a1.id}/documents/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        docs = _get_items(res)
        self.assertEqual(len(docs), 1)

        # Admin A CANNOT list foreign service docs -> 404
        res = self.client.get(f'/api/services/{self.srv_b1.id}/documents/')
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

        # Staff A can read own service docs
        self.client.force_authenticate(user=self.staff_a)
        res = self.client.get(f'/api/services/{self.srv_a1.id}/documents/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        docs = _get_items(res)
        self.assertEqual(len(docs), 1)

        # Staff A CANNOT create a doc -> 403
        res = self.client.post(f'/api/services/{self.srv_a1.id}/documents/', data={
            'document_name': 'Staff Doc',
            'is_mandatory': True,
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # Admin A can create doc on own service -> 201
        self.client.force_authenticate(user=self.admin_a)
        res = self.client.post(f'/api/services/{self.srv_a1.id}/documents/', data={
            'document_name': 'Admin Doc',
            'is_mandatory': True,
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        # Admin A CANNOT create doc on foreign service -> 404
        res = self.client.post(f'/api/services/{self.srv_b1.id}/documents/', data={
            'document_name': 'Foreign Doc',
            'is_mandatory': True,
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    # ─────────────────────────────────────────────────────────────────────────
    # 8. WorkflowStep Scoping & Authentication Security
    # ─────────────────────────────────────────────────────────────────────────

    def test_workflow_step_scoping_and_security(self):
        # 1. Unauthenticated access is blocked (formerly AllowAny vulnerability)
        res = self.client.get(f'/api/services/{self.srv_a1.id}/workflow-steps/')
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

        # 2. Admin A can list own service steps
        self.client.force_authenticate(user=self.admin_a)
        res = self.client.get(f'/api/services/{self.srv_a1.id}/workflow-steps/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        steps = _get_items(res)
        self.assertEqual(len(steps), 1)

        # 3. Admin A CANNOT list foreign service steps -> 404
        res = self.client.get(f'/api/services/{self.srv_b1.id}/workflow-steps/')
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

        # 4. Staff A can read own service steps
        self.client.force_authenticate(user=self.staff_a)
        res = self.client.get(f'/api/services/{self.srv_a1.id}/workflow-steps/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        steps = _get_items(res)
        self.assertEqual(len(steps), 1)

        # 5. Staff A CANNOT create workflow step -> 403
        res = self.client.post(f'/api/services/{self.srv_a1.id}/workflow-steps/', data={
            'step_name': 'Staff Step',
            'step_order': 2,
            'responsible_role_id': self.role_dept_admin.id,
            'action_type': 'APPROVAL',
            'allowed_actions': ['APPROVE'],
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # 6. Admin A can create step on own service -> 201
        self.client.force_authenticate(user=self.admin_a)
        res = self.client.post(f'/api/services/{self.srv_a1.id}/workflow-steps/', data={
            'step_name': 'Admin Step 2',
            'step_order': 2,
            'responsible_role_id': self.role_dept_admin.id,
            'action_type': 'APPROVAL',
            'allowed_actions': ['APPROVE'],
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        # 7. Admin A CANNOT create step on foreign service -> 404
        res = self.client.post(f'/api/services/{self.srv_b1.id}/workflow-steps/', data={
            'step_name': 'Foreign Step',
            'step_order': 2,
            'responsible_role_id': self.role_dept_admin.id,
            'action_type': 'APPROVAL',
            'allowed_actions': ['APPROVE'],
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
