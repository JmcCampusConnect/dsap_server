import re

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import transaction
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.students.models import Student
from common.exceptions import (
    EmailExistsError,
    FieldNotEditableError,
    ProfileNotFoundError,
    ValidationFailedError,
)

from .serializers import (
    StaffProfileSerializer,
    StudentAcademicSerializer,
    StudentContactSerializer,
    StudentPersonalSerializer,
)


# ---------------------------------------------------------------------
# Allow-lists & constants
# ---------------------------------------------------------------------
STUDENT_EDITABLE = {"mobile_number", "email"}
STAFF_EDITABLE = {"email"}

MOBILE_RE = re.compile(r"^[6-9]\d{9}$")

# Sentinel used only for the "empty PATCH body" error details key.
_BODY_KEY = "__request__"


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def _is_student(user) -> bool:
    return getattr(user.role_id, "name", None) == "STUDENT"


def _normalize_mobile(value) -> str:
    """Strip, validate, and normalize as a 10-digit Indian mobile number."""
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    if not MOBILE_RE.match(digits):
        raise ValidationFailedError(
            {"mobile_number": ["Mobile number must be a valid 10-digit Indian number."]}
        )
    return digits


def _normalize_email(value) -> str:
    """Lowercase, strip, and validate as an email address."""
    email = str(value or "").strip().lower()
    if not email:
        raise ValidationFailedError({"email": ["Email cannot be empty."]})
    try:
        validate_email(email)
    except DjangoValidationError:
        raise ValidationFailedError({"email": ["Enter a valid email address."]})
    return email


# ---------------------------------------------------------------------
# View
# ---------------------------------------------------------------------
class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    # -- READ ---------------------------------------------------------
    def get(self, request):
        return self._build_response(request.user)

    # -- WRITE --------------------------------------------------------
    def patch(self, request):
        user = request.user
        payload = request.data

        if not isinstance(payload, dict) or not payload:
            raise ValidationFailedError(
                {_BODY_KEY: ["Request body must be a non-empty JSON object."]}
            )

        editable = STUDENT_EDITABLE if _is_student(user) else STAFF_EDITABLE
        forbidden = sorted(set(payload.keys()) - editable)
        if forbidden:
            # Reject the whole request — do not apply a partial update.
            raise FieldNotEditableError(forbidden)

        new_email = _normalize_email(payload["email"]) if "email" in payload else None
        new_mobile = (
            _normalize_mobile(payload["mobile_number"])
            if "mobile_number" in payload
            else None
        )

        with transaction.atomic():
            user_changes = {}
            student_changes = {}

            # --- User.email (any role) -------------------------------
            if new_email is not None:
                old_email = (user.email or "").lower()
                if old_email != new_email:
                    if (
                        User.objects
                        .filter(email__iexact=new_email)
                        .exclude(pk=user.pk)
                        .exists()
                    ):
                        raise EmailExistsError()
                    user_changes["email"] = {"old": old_email or None, "new": new_email}
                    user.email = new_email
                    user.save(update_fields=["email", "updated_at"])

            # --- Student.mobile_number (students only) ---------------
            if new_mobile is not None:
                try:
                    student = Student.objects.select_related(
                        "user_id", "academic_department_id"
                    ).get(user_id=user)
                except Student.DoesNotExist:
                    raise ProfileNotFoundError()

                old_mobile = student.mobile_number
                if old_mobile != new_mobile:
                    student.mobile_number = new_mobile
                    student.save(update_fields=["mobile_number", "updated_at"])
                    student_changes["mobile_number"] = {
                        "old": old_mobile,
                        "new": new_mobile,
                    }

            # --- Audit trail -----------------------------------------
            if user_changes:
                AuditLog.log(
                    request=request,
                    action="UPDATE",
                    obj=user,
                    changes=user_changes,
                )
            if student_changes:
                AuditLog.log(
                    request=request,
                    action="UPDATE",
                    obj=student,
                    changes=student_changes,
                )

        return self._build_response(user)

    # -- Response assembly -------------------------------------------
    def _build_response(self, user):
        if _is_student(user):
            try:
                student = (
                    Student.objects
                    .select_related("user_id", "academic_department_id")
                    .get(user_id=user)
                )
            except Student.DoesNotExist:
                raise ProfileNotFoundError()

            return Response(
                {
                    "role": "STUDENT",
                    "id": user.id,
                    "username": user.username,
                    "profile": StudentPersonalSerializer(student).data,
                    "academic": StudentAcademicSerializer(student).data,
                    "contact": StudentContactSerializer(student).data,
                    "created_at": student.created_at,
                    "updated_at": student.updated_at,
                }
            )

        fresh_user = (
            User.objects
            .select_related(
                "role_id", "service_department_id", "academic_department_id"
            )
            .get(pk=user.pk)
        )
        return Response(StaffProfileSerializer(fresh_user).data)