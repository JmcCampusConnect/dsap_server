from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.documents.models import Document
from apps.departments.models import AcademicDepartment, ServiceDepartment
from apps.requests.models import Request
from apps.services.models import Service, ServiceDocument
from apps.students.models import Student
from apps.workflow.models import WorkflowStep


class RequestStatusFlowTestCase(TestCase):
    def setUp(self):
        staff_role = Role.objects.create(name="SERVICE_DEPT_STAFF")
        department = ServiceDepartment.objects.create(
            code="STATUS-TEST",
            name="Status Test Department",
        )
        staff = User.objects.create(
            username="status-test-staff",
            email="status-test-staff@example.test",
            password_hash="not-a-real-password",
            role_id=staff_role,
            service_department_id=department,
        )
        academic_department = AcademicDepartment.objects.create(
            code="STATUS-TEST",
            stream="Aided",
            degree="B.Sc.",
            branch="Computer Science",
            type="UG",
            category="SCIENCE",
        )
        student_role = Role.objects.create(name="STUDENT")
        student_user = User.objects.create(
            username="status-test-student",
            email="status-test-student@example.test",
            password_hash="not-a-real-password",
            role_id=student_role,
        )
        self.student_user = student_user
        student = Student.objects.create(
            register_number="STATUS-TEST-001",
            name="Status Test Student",
            user_id=student_user,
            academic_department_id=academic_department,
            year_of_admission="2024",
            mobile_number="0000000000",
        )
        service = Service.objects.create(
            code="STATUS-TEST",
            name="Status Test Service",
            service_department_id=department,
        )
        verification_step = WorkflowStep.objects.create(
            service_id=service,
            step_order=1,
            step_name="Document Verification",
            step_kind="VERIFICATION",
            responsible_role_id=staff_role,
            allowed_actions=["FORWARD", "RETURN", "REJECT"],
        )
        WorkflowStep.objects.create(
            service_id=service,
            step_order=2,
            step_name="Service Processing",
            step_kind="PROCESSING",
            responsible_role_id=staff_role,
            allowed_actions=["FORWARD", "REJECT"],
        )
        documents = [
            ServiceDocument.objects.create(
                service_id=service,
                document_name=f"Required Document {index}",
                is_mandatory=True,
            )
            for index in (1, 2)
        ]
        request = Request.objects.create(
            request_number="STATUS-TEST-REQUEST",
            student_id=student,
            service_id=service,
            current_status="SUBMITTED",
            current_step_id=verification_step,
            submitted_at=timezone.now(),
        )
        self.documents = [
            Document.objects.create(
                request_id=request,
                service_document_id=service_document,
                file_path=f"status-test/document-{index}.pdf",
                file_hash="a" * 64,
                verification_status="PENDING",
            )
            for index, service_document in enumerate(documents, start=1)
        ]
        self.request = request
        self.client = APIClient()
        self.client.force_authenticate(user=staff)

    def test_verified_status_requires_all_documents_and_forward_enters_processing(self):
        response = self.client.patch(
            f"/api/department-queue/{self.request.id}/documents/{self.documents[0].id}/",
            {"verification_status": "VERIFIED"},
            format="json",
            HTTP_HOST="localhost",
        )
        self.assertEqual(response.status_code, 200)

        self.request.refresh_from_db()
        self.assertEqual(self.request.current_status, "SUBMITTED")

        response = self.client.patch(
            f"/api/department-queue/{self.request.id}/documents/{self.documents[1].id}/",
            {"verification_status": "VERIFIED"},
            format="json",
            HTTP_HOST="localhost",
        )
        self.assertEqual(response.status_code, 200)
        self.request.refresh_from_db()
        self.assertEqual(self.request.current_status, "VERIFIED")

        verified_queue = self.client.get(
            "/api/department-queue/?status=VERIFIED",
            HTTP_HOST="localhost",
        )
        self.assertEqual(verified_queue.status_code, 200)
        self.assertEqual(
            [item["id"] for item in verified_queue.data["results"]],
            [self.request.id],
        )

        self.client.force_authenticate(user=self.student_user)
        student_stats = self.client.get(
            "/api/requests/my/stats/",
            HTTP_HOST="localhost",
        )
        self.assertEqual(student_stats.status_code, 200)
        self.assertEqual(student_stats.data["VERIFIED"], 1)
        self.client.force_authenticate(
            user=User.objects.get(username="status-test-staff")
        )

        response = self.client.post(
            f"/api/department-queue/{self.request.id}/forward/",
            {"remarks": "Documents verified"},
            format="json",
            HTTP_HOST="localhost",
        )
        self.assertEqual(response.status_code, 200)
        self.request.refresh_from_db()
        self.assertEqual(self.request.current_status, "PROCESSING")

        processing_queue = self.client.get(
            "/api/department-queue/?status=PROCESSING",
            HTTP_HOST="localhost",
        )
        self.assertEqual(processing_queue.status_code, 200)
        self.assertEqual(
            [item["id"] for item in processing_queue.data["results"]],
            [self.request.id],
        )
        self.client.force_authenticate(user=self.student_user)
        student_stats = self.client.get(
            "/api/requests/my/stats/",
            HTTP_HOST="localhost",
        )
        self.assertEqual(student_stats.status_code, 200)
        self.assertEqual(student_stats.data["PROCESSING"], 1)
