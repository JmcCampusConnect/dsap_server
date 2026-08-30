from django.test import TestCase
from rest_framework import serializers

from apps.accounts.models import Role, User
from apps.departments.models import AcademicDepartment

from .models import Student
from .serializers import StudentSerializer


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
        self.assertEqual(student.user_id.academic_department_id_id, self.department.id)
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

        self.assertIn('Department not found.', str(context.exception))

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

    def test_update_student_syncs_academic_department_to_user(self):
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

        update_serializer = StudentSerializer(
            instance=student,
            data={
                'register_number': '12MTH0003',
                'name': 'Sync Student',
                'year_of_admission': '2026',
                'dob': '01-01-2006',
                'stream': 'SFM',
                'mobile_number': '9876543212',
                'status': False,
                'academic_department_id': updated_department.id,
                'role_id': self.student_role.id,
            }
        )

        self.assertTrue(update_serializer.is_valid(), update_serializer.errors)
        updated_student = update_serializer.save()

        self.assertEqual(updated_student.academic_department_id_id, updated_department.id)
        self.assertEqual(updated_student.user_id.academic_department_id_id, updated_department.id)
