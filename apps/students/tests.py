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
                'status': 'active',
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
                'status': 'active',
                'role_id': self.student_role.id,
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

        with self.assertRaises(serializers.ValidationError) as context:
            serializer.save()

        self.assertIn('Department not found.', str(context.exception))
