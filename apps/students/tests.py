import datetime as dt
import io

import openpyxl
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.test import APIClient, APIRequestFactory

from apps.accounts.role_constants import Roles
from apps.audit.models import AuditLog

from apps.accounts.models import Role, User
from apps.departments.models import AcademicDepartment

from .models import Student
from .serializers import StudentSerializer
from .views import StudentViewSet


class StudentSerializerDepartmentTests(TestCase):
    def setUp(self):
        self.student_role = Role.objects.create(name='STUDENT', description='Student role')
        self.department = AcademicDepartment.objects.create(
            code='CSE',
            stream='SFM',
            degree='B.Sc',
            branch='Computer Science',
            type='UG',
            category='SCIENCE',
        )
        self.aided_department = AcademicDepartment.objects.create(
            code='CSE',
            stream='Aided',
            degree='B.Sc',
            branch='Computer Science',
            type='UG',
            category='SCIENCE',
        )

    def test_create_student_derives_department_from_register_number(self):
        serializer = StudentSerializer(
            data={
                'register_number': '12CSE0001',
                'name': 'John Doe',
                'year_of_admission': '2026',
                'dob': '01-01-2006',
                'stream': 'SFM',
                'mobile_number': '9876543210',
                'status': True,
                'email': 'john.doe@example.com',
                'role_id': self.student_role.id,
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        student = serializer.save()

        self.assertEqual(student.academic_department_id_id, self.department.id)
        self.assertEqual(student.user_id.username, '12CSE0001')
        self.assertTrue(User.objects.filter(username='12CSE0001').exists())
        self.assertTrue(Student.objects.filter(register_number='12CSE0001').exists())

    def test_create_student_returns_error_when_department_code_is_missing(self):
        serializer = StudentSerializer(
            data={
                'register_number': '12XYZ0001',
                'name': 'Jane Doe',
                'year_of_admission': '2026',
                'dob': '01-01-2006',
                'stream': 'SFM',
                'mobile_number': '9876543210',
                'status': True,
                'role_id': self.student_role.id,
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

        with self.assertRaises(serializers.ValidationError) as context:
            serializer.save()

        self.assertIn('Department not found for the selected stream.', str(context.exception))

    def test_create_student_accepts_aided_stream_value(self):
        serializer = StudentSerializer(
            data={
                'register_number': '12CSE0002',
                'name': 'Aided Student',
                'year_of_admission': '2026',
                'dob': '01-01-2006',
                'stream': 'Aided',
                'mobile_number': '9876543211',
                'status': True,
                'email': 'aided.student@example.com',
                'role_id': self.student_role.id,
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        student = serializer.save()

        self.assertEqual(student.academic_department_id_id, self.aided_department.id)
        self.assertEqual(student.stream, 'AIDED')
        self.assertEqual(student.user_id.username, '12CSE0002')
        self.assertEqual(Student.objects.get(register_number='12CSE0002').stream, 'AIDED')

    def test_create_student_accepts_inactive_status(self):
        serializer = StudentSerializer(
            data={
                'register_number': '12CSE0004',
                'name': 'Inactive Student',
                'year_of_admission': '2026',
                'dob': '01-01-2006',
                'stream': 'SFM',
                'mobile_number': '9876543213',
                'status': False,
                'email': 'inactive.student@example.com',
                'role_id': self.student_role.id,
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        student = serializer.save()

        self.assertFalse(student.status)
        self.assertFalse(student.user_id.is_active)

    def test_create_student_rejects_duplicate_email(self):
        User.objects.create(
            username='12CSE0099',
            email='existing.student@example.com',
            password_hash='hashed-password',
            role_id=self.student_role,
            is_active=True,
        )

        serializer = StudentSerializer(
            data={
                'register_number': '12CSE0005',
                'name': 'Duplicate Email Student',
                'year_of_admission': '2026',
                'dob': '01-01-2006',
                'stream': 'SFM',
                'mobile_number': '9876543214',
                'status': True,
                'email': 'existing.student@example.com',
                'role_id': self.student_role.id,
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertEqual(
            serializer.errors['email'][0],
            'A user with this email already exists.'
        )

    def test_update_student_derives_academic_department_from_register_number(self):
        serializer = StudentSerializer(
            data={
                'register_number': '12CSE0003',
                'name': 'Sync Student',
                'year_of_admission': '2026',
                'dob': '01-01-2006',
                'stream': 'SFM',
                'mobile_number': '9876543212',
                'status': True,
                'email': 'sync.student@example.com',
                'role_id': self.student_role.id,
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        student = serializer.save()

        updated_department = AcademicDepartment.objects.create(
            code='MTH',
            stream='SFM',
            degree='B.Sc',
            branch='Mathematics',
            type='UG',
            category='SCIENCE',
        )
        updated_aided_department = AcademicDepartment.objects.create(
            code='MTH',
            stream='Aided',
            degree='B.Sc',
            branch='Mathematics',
            type='UG',
            category='SCIENCE',
        )

        update_serializer = StudentSerializer(
            instance=student,
            data={
                'register_number': '12MTH0003',
                'name': 'Sync Student',
                'year_of_admission': '2026',
                'dob': '01-01-2006',
                'stream': 'Aided',
                'mobile_number': '9876543212',
                'status': False,
                'academic_department_id': updated_department.id,
                'role_id': self.student_role.id,
            }
        )

        self.assertTrue(update_serializer.is_valid(), update_serializer.errors)
        updated_student = update_serializer.save()

        self.assertEqual(updated_student.academic_department_id_id, updated_aided_department.id)
        self.assertEqual(updated_student.user_id.username, '12MTH0003')


class StudentViewSetGraduateFilterTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.student_role = Role.objects.create(name='STUDENT', description='Student role')
        self.ug_department = AcademicDepartment.objects.create(
            code='CSE',
            stream='SFM',
            degree='B.Tech',
            branch='Computer Science',
            type='UG',
            category='SCIENCE',
        )
        self.pg_department = AcademicDepartment.objects.create(
            code='MCS',
            stream='SFM',
            degree='M.Tech',
            branch='Computer Science',
            type='PG',
            category='SCIENCE',
        )
        self.ug_student = Student.objects.create(
            register_number='22CSE0001',
            name='UG Student',
            user_id=User.objects.create(
                username='22CSE0001',
                email='ug.student@example.com',
                password_hash='hashed-password',
                role_id=self.student_role,
                is_active=True,
            ),
            academic_department_id=self.ug_department,
            year_of_admission='2022',
            stream='SFM',
            mobile_number='9876543210',
            status=True,
        )
        self.pg_student = Student.objects.create(
            register_number='22MCS0001',
            name='PG Student',
            user_id=User.objects.create(
                username='22MCS0001',
                email='pg.student@example.com',
                password_hash='hashed-password',
                role_id=self.student_role,
                is_active=True,
            ),
            academic_department_id=self.pg_department,
            year_of_admission='2022',
            stream='SFM',
            mobile_number='9876543211',
            status=True,
        )

    def test_get_queryset_filters_students_by_graduate_type(self):
        request = self.factory.get('/students/', {'graduate': 'UG'})
        view = StudentViewSet()
        view.request = Request(request)

        queryset = view.get_queryset()

        self.assertEqual(list(queryset.values_list('id', flat=True)), [self.ug_student.id])

        request = self.factory.get('/students/', {'graduate': 'PG'})
        view = StudentViewSet()
        view.request = Request(request)

        queryset = view.get_queryset()

        self.assertEqual(list(queryset.values_list('id', flat=True)), [self.pg_student.id])

    def test_get_queryset_filters_all_stream_variants_of_department_code(self):
        other_stream_department = AcademicDepartment.objects.create(
            code='CSE',
            stream='SFW',
            degree='B.Tech',
            branch='Computer Science',
            type='UG',
            category='SCIENCE',
        )
        other_stream_user = User.objects.create(
            username='22CSE0002',
            email='ug.student2@example.com',
            password_hash='hashed-password',
            role_id=self.student_role,
            is_active=True,
        )
        other_stream_student = Student.objects.create(
            register_number='22CSE0002',
            name='UG Student Second Stream',
            user_id=other_stream_user,
            academic_department_id=other_stream_department,
            year_of_admission='2022',
            stream='SFW',
            mobile_number='9876543212',
            status=True,
        )
        request = self.factory.get('/students/', {'academic_department_code': 'CSE'})
        view = StudentViewSet()
        view.request = Request(request)

        queryset = view.get_queryset()

        self.assertCountEqual(
            queryset.values_list('id', flat=True),
            [self.ug_student.id, other_stream_student.id],
        )


class StudentExcelExportTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_role = Role.objects.create(name=Roles.SYSTEM_ADMIN, description='System Admin')
        self.student_role = Role.objects.create(name=Roles.STUDENT, description='Student')

        self.admin_user = User.objects.create(
            username='export_admin',
            email='export.admin@example.com',
            password_hash='hashed-password',
            role_id=self.admin_role,
            is_active=True,
        )

        self.ug_dept = AcademicDepartment.objects.create(
            code='UCS',
            stream='Aided',
            degree='B.Sc.',
            branch='Computer Science',
            type='UG',
            category='SCIENCE',
        )
        self.pg_dept = AcademicDepartment.objects.create(
            code='MCA',
            stream='SFM',
            degree='M.C.A.',
            branch='Computer Applications',
            type='PG',
            category='SCIENCE',
        )

        self.active_user = User.objects.create(
            username='24UCS001',
            email='ug.student@example.com',
            password_hash='hashed-password',
            role_id=self.student_role,
            is_active=True,
        )
        self.active_student = Student.objects.create(
            register_number='24UCS001',
            name='UG Active Student',
            dob=dt.date(2005, 5, 12),
            user_id=self.active_user,
            academic_department_id=self.ug_dept,
            year_of_admission='2024',
            section='A',
            stream=Student.StreamChoices.AIDED,
            mobile_number='9876543210',
            status=True,
        )

        self.inactive_user = User.objects.create(
            username='24MCA002',
            email=None,
            password_hash='hashed-password',
            role_id=self.student_role,
            is_active=False,
        )
        self.inactive_student = Student.objects.create(
            register_number='24MCA002',
            name='PG Inactive Student',
            dob=None,
            user_id=self.inactive_user,
            academic_department_id=self.pg_dept,
            year_of_admission='2024',
            section=None,
            stream=Student.StreamChoices.SFM,
            mobile_number='9123456789',
            status=False,
        )

    def test_export_excel_headers_and_field_mappings_including_inactive(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(
            '/api/students/export/?include_inactive=true',
            HTTP_HOST='localhost',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        self.assertIn('attachment; filename=students.xlsx', response['Content-Disposition'])

        wb = openpyxl.load_workbook(io.BytesIO(response.content))
        ws = wb.active
        self.assertEqual(ws.title, 'Students')

        rows = list(ws.iter_rows(values_only=True))
        self.assertEqual(len(rows), 3)

        expected_headers = (
            'Register Number',
            'Name',
            'Email',
            'Department Name',
            'Program Type',
            'Year of Admission',
            'DOB (DD-MM-YYYY)',
            'Section',
            'Stream',
            'Mobile Number',
            'Status',
        )
        self.assertEqual(rows[0], expected_headers)
        self.assertEqual(ws.max_column, len(expected_headers))

        rows_by_reg = {row[0]: row for row in rows[1:]}
        self.assertEqual(set(rows_by_reg.keys()), {'24UCS001', '24MCA002'})

        self.assertEqual(
            rows_by_reg['24MCA002'],
            (
                '24MCA002',
                'PG Inactive Student',
                None,
                'M.C.A. - Computer Applications',
                'PG',
                '2024',
                None,
                None,
                'SFM',
                '9123456789',
                'Inactive',
            ),
        )
        self.assertEqual(
            rows_by_reg['24UCS001'],
            (
                '24UCS001',
                'UG Active Student',
                'ug.student@example.com',
                'B.Sc. - Computer Science',
                'UG',
                '2024',
                '12-05-2005',
                'A',
                'Aided',
                '9876543210',
                'Active',
            ),
        )
        self.assertIsInstance(rows_by_reg['24MCA002'][-1], str)
        self.assertIsInstance(rows_by_reg['24UCS001'][-1], str)

        audit_log = AuditLog.objects.filter(
            action='EXPORT',
            object_id='EXPORT_STUDENTS',
        ).first()
        self.assertIsNotNone(audit_log)
        self.assertEqual(audit_log.changes, {'exported_count': 2})

    def test_export_excel_defaults_to_active_students_only(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get('/api/students/export/', HTTP_HOST='localhost')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        wb = openpyxl.load_workbook(io.BytesIO(response.content))
        rows = list(wb.active.iter_rows(values_only=True))

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][0], '24UCS001')
        self.assertEqual(rows[1][-1], 'Active')

    def test_export_excel_forbidden_for_student_role(self):
        self.client.force_authenticate(user=self.active_user)
        response = self.client.get('/api/students/export/', HTTP_HOST='localhost')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class StudentExcelImportTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_role = Role.objects.create(name=Roles.SYSTEM_ADMIN, description='System Admin')
        self.student_role = Role.objects.create(name=Roles.STUDENT, description='Student')

        self.admin_user = User.objects.create(
            username='import_admin',
            email='import.admin@example.com',
            password_hash='hashed-password',
            role_id=self.admin_role,
            is_active=True,
        )

        self.ug_aided_dept = AcademicDepartment.objects.create(
            code='UCS',
            stream='Aided',
            degree='B.Sc.',
            branch='Computer Science',
            type='UG',
            category='SCIENCE',
        )
        self.ug_sfm_dept = AcademicDepartment.objects.create(
            code='UCS',
            stream='SFM',
            degree='B.Sc.',
            branch='Computer Science',
            type='UG',
            category='SCIENCE',
        )
        self.pg_dept = AcademicDepartment.objects.create(
            code='MCA',
            stream='SFM',
            degree='M.C.A.',
            branch='Computer Applications',
            type='PG',
            category='SCIENCE',
        )

    @staticmethod
    def _build_xlsx_upload(rows, filename='students_import.xlsx'):
        wb = openpyxl.Workbook()
        ws = wb.active
        for row in rows:
            ws.append(row)
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return SimpleUploadedFile(
            filename,
            buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

    def test_import_and_export_header_definitions(self):
        from apps.students.views import StudentViewSet

        self.assertEqual(len(StudentViewSet.EXCEL_HEADERS), 11)
        self.assertEqual(len(StudentViewSet.IMPORT_HEADERS), 10)
        self.assertNotIn('Status', StudentViewSet.IMPORT_HEADERS)
        self.assertEqual(StudentViewSet.EXCEL_HEADERS[-1], 'Status')
        self.assertEqual(StudentViewSet.IMPORT_HEADERS, StudentViewSet.EXCEL_HEADERS[:-1])

    def test_import_excel_10_columns_creates_active_students_with_department_and_program_type(self):
        self.client.force_authenticate(user=self.admin_user)

        upload = self._build_xlsx_upload([
            [
                'Register Number',
                'Name',
                'Email',
                'Department Name',
                'Program Type',
                'Year of Admission',
                'DOB (DD-MM-YYYY)',
                'Section',
                'Stream',
                'Mobile Number',
            ],
            [
                '24UCS101',
                'Alice UG',
                'alice.ug@example.com',
                'B.Sc. - Computer Science',
                'UG',
                '2024',
                '15-03-2005',
                'A',
                'SFM',
                '9876543210',
            ],
            [
                '24MCA102',
                'Bob PG',
                'bob.pg@example.com',
                'M.C.A. - Computer Applications',
                'PG',
                '2024',
                '20-07-2002',
                'B',
                'SFM',
                '9876543211',
            ],
        ])

        response = self.client.post(
            '/api/students/import/',
            {'file': upload},
            format='multipart',
            HTTP_HOST='localhost',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['imported_count'], 2)
        self.assertEqual(
            response.data['uploaded_register_numbers'],
            ['24UCS101', '24MCA102'],
        )

        alice = Student.objects.select_related('user_id', 'academic_department_id').get(
            register_number='24UCS101'
        )
        self.assertEqual(alice.academic_department_id_id, self.ug_sfm_dept.id)
        self.assertEqual(alice.academic_department_id.name, 'B.Sc. - Computer Science')
        self.assertEqual(alice.academic_department_id.type, 'UG')
        self.assertEqual(alice.stream, 'SFM')
        self.assertTrue(alice.status)
        self.assertTrue(alice.user_id.is_active)

        bob = Student.objects.select_related('user_id', 'academic_department_id').get(
            register_number='24MCA102'
        )
        self.assertEqual(bob.academic_department_id_id, self.pg_dept.id)
        self.assertEqual(bob.academic_department_id.name, 'M.C.A. - Computer Applications')
        self.assertEqual(bob.academic_department_id.type, 'PG')
        self.assertTrue(bob.status)
        self.assertTrue(bob.user_id.is_active)

        audit_log = AuditLog.objects.filter(
            action='IMPORT',
            object_id='BULK_IMPORT',
        ).first()
        self.assertIsNotNone(audit_log)
        self.assertEqual(audit_log.changes, {'imported_count': 2})

    def test_import_excel_ignores_status_and_preserves_existing_student_status(self):
        self.client.force_authenticate(user=self.admin_user)

        inactive_user = User.objects.create(
            username='24UCS201',
            email='inactive.student@example.com',
            password_hash='hashed-password',
            role_id=self.student_role,
            is_active=False,
        )
        inactive_student = Student.objects.create(
            register_number='24UCS201',
            name='Inactive Student',
            dob=dt.date(2005, 1, 10),
            user_id=inactive_user,
            academic_department_id=self.ug_aided_dept,
            year_of_admission='2024',
            section='A',
            stream=Student.StreamChoices.AIDED,
            mobile_number='9876543222',
            status=False,
        )

        active_user = User.objects.create(
            username='24UCS203',
            email='active.student@example.com',
            password_hash='hashed-password',
            role_id=self.student_role,
            is_active=True,
        )
        active_student = Student.objects.create(
            register_number='24UCS203',
            name='Active Student',
            dob=dt.date(2005, 2, 11),
            user_id=active_user,
            academic_department_id=self.ug_aided_dept,
            year_of_admission='2024',
            section='A',
            stream=Student.StreamChoices.AIDED,
            mobile_number='9876543223',
            status=True,
        )

        export_res = self.client.get(
            '/api/students/export/?include_inactive=true',
            HTTP_HOST='localhost',
        )
        self.assertEqual(export_res.status_code, status.HTTP_200_OK)

        wb = openpyxl.load_workbook(io.BytesIO(export_res.content))
        ws = wb.active
        exported_rows = list(ws.iter_rows(values_only=True))
        self.assertEqual(len(exported_rows[0]), 11)
        self.assertEqual(len(exported_rows), 3)

        row_inactive_flipped = list(exported_rows[1])
        row_inactive_flipped[-1] = 'Active'

        row_active_flipped = list(exported_rows[2])
        row_active_flipped[-1] = 'Inactive'

        new_row = list(exported_rows[1])
        new_row[0] = '24UCS202'
        new_row[1] = 'Roundtrip Student'
        new_row[2] = 'roundtrip.student@example.com'
        new_row[-1] = 'Inactive'

        upload = self._build_xlsx_upload(
            [list(exported_rows[0]), row_inactive_flipped, row_active_flipped, new_row],
            filename='roundtrip.xlsx',
        )
        import_res = self.client.post(
            '/api/students/import/',
            {'file': upload},
            format='multipart',
            HTTP_HOST='localhost',
        )

        self.assertEqual(import_res.status_code, status.HTTP_201_CREATED, import_res.data)
        self.assertEqual(import_res.data['imported_count'], 1)
        self.assertEqual(import_res.data['uploaded_register_numbers'], ['24UCS202'])
        self.assertEqual(
            import_res.data['already_existing_register_numbers'],
            ['24UCS201', '24UCS203'],
        )

        imported = Student.objects.select_related('user_id', 'academic_department_id').get(
            register_number='24UCS202'
        )
        self.assertEqual(imported.academic_department_id_id, self.ug_aided_dept.id)
        self.assertEqual(imported.academic_department_id.name, 'B.Sc. - Computer Science')
        self.assertEqual(imported.academic_department_id.type, 'UG')
        self.assertEqual(imported.stream, 'AIDED')
        self.assertTrue(imported.status)
        self.assertTrue(imported.user_id.is_active)

        inactive_student.refresh_from_db()
        inactive_user.refresh_from_db()
        self.assertFalse(inactive_student.status)
        self.assertFalse(inactive_user.is_active)

        active_student.refresh_from_db()
        active_user.refresh_from_db()
        self.assertTrue(active_student.status)
        self.assertTrue(active_user.is_active)

    def test_import_excel_rejects_mismatched_or_invalid_department_and_program_type(self):
        self.client.force_authenticate(user=self.admin_user)

        upload = self._build_xlsx_upload([
            [
                'Register Number',
                'Name',
                'Email',
                'Department Name',
                'Program Type',
                'Year of Admission',
                'DOB (DD-MM-YYYY)',
                'Section',
                'Stream',
                'Mobile Number',
            ],
            [
                '24UCS301',
                'Mismatch Student',
                'mismatch@example.com',
                'M.C.A. - Computer Applications',
                'PG',
                '2024',
                '15-03-2005',
                'A',
                'SFM',
                '9876543210',
            ],
            [
                '24MCA302',
                'Invalid Program Type',
                'invalid.pt@example.com',
                'M.C.A. - Computer Applications',
                'PhD',
                '2024',
                '20-07-2002',
                'A',
                'SFM',
                '9876543211',
            ],
        ])

        response = self.client.post(
            '/api/students/import/',
            {'file': upload},
            format='multipart',
            HTTP_HOST='localhost',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        details = response.data['details']
        self.assertEqual(len(details), 2)
        self.assertIn("Department Name 'M.C.A. - Computer Applications' does not match", details[0]['errors'][0])
        self.assertIn("Program Type 'PG' does not match 'UG'", details[0]['errors'][1])
        self.assertIn('Program Type must be one of: UG, PG.', details[1]['errors'][0])

    def test_import_excel_supports_legacy_format_and_blank_department_cells(self):
        self.client.force_authenticate(user=self.admin_user)

        upload_legacy = self._build_xlsx_upload([
            [
                'Register Number',
                'Name',
                'Email',
                'Year of Admission',
                'DOB (DD-MM-YYYY)',
                'Section',
                'Stream',
                'Mobile Number',
            ],
            [
                '24UCS401',
                'Legacy Student',
                'legacy@example.com',
                '2024',
                '01-02-2005',
                'A',
                'Aided',
                '9876543233',
            ],
        ])

        res_legacy = self.client.post(
            '/api/students/import/',
            {'file': upload_legacy},
            format='multipart',
            HTTP_HOST='localhost',
        )
        self.assertEqual(res_legacy.status_code, status.HTTP_201_CREATED, res_legacy.data)
        legacy_student = Student.objects.select_related('academic_department_id').get(
            register_number='24UCS401'
        )
        self.assertEqual(legacy_student.academic_department_id_id, self.ug_aided_dept.id)
        self.assertTrue(legacy_student.status)

        upload_blank_10 = self._build_xlsx_upload([
            [
                'Register Number',
                'Name',
                'Email',
                'Department Name',
                'Program Type',
                'Year of Admission',
                'DOB (DD-MM-YYYY)',
                'Section',
                'Stream',
                'Mobile Number',
            ],
            [
                '24MCA402',
                'Blank Dept Cells',
                'blank.dept@example.com',
                '',
                '',
                '2024',
                '05-06-2002',
                'A',
                'SFM',
                '9876543244',
            ],
        ])

        res_blank = self.client.post(
            '/api/students/import/',
            {'file': upload_blank_10},
            format='multipart',
            HTTP_HOST='localhost',
        )
        self.assertEqual(res_blank.status_code, status.HTTP_201_CREATED, res_blank.data)
        blank_student = Student.objects.select_related('academic_department_id').get(
            register_number='24MCA402'
        )
        self.assertEqual(blank_student.academic_department_id_id, self.pg_dept.id)
        self.assertTrue(blank_student.status)
