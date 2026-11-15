"""
Recipient Resolver Service.
Resolves and validates student recipient email addresses from trusted request/student relationships.
"""

from dataclasses import dataclass
import logging
from typing import Any

from django.core.exceptions import ValidationError
from django.core.validators import validate_email

logger = logging.getLogger(__name__)


@dataclass
class ResolvedRecipient:
    user: Any | None
    email: str
    student_name: str
    register_number: str
    is_valid: bool = True
    error_message: str = ""


def resolve_request_recipient(request_obj) -> ResolvedRecipient:
    """
    Given a Request model instance, resolve the student recipient and their registered email address.
    """
    if not request_obj:
        return ResolvedRecipient(
            user=None,
            email="",
            student_name="",
            register_number="",
            is_valid=False,
            error_message="No request instance provided.",
        )

    email = ""
    student_user = None
    student_name = ""
    register_number = ""
    try:
        student = request_obj.student_id
        if not student:
            return ResolvedRecipient(
                user=None,
                email="",
                student_name="",
                register_number="",
                is_valid=False,
                error_message=f"Request {request_obj.request_number} has no associated student.",
            )

        student_user = student.user_id
        student_name = student.name or ""
        register_number = student.register_number or ""

        email = (student_user.email or "").strip() if student_user else ""
        if not email:
            logger.warning(
                "Recipient resolution failed: Student %s (user %s) has no registered email address.",
                register_number,
                getattr(student_user, "id", None),
            )
            return ResolvedRecipient(
                user=student_user,
                email="",
                student_name=student_name,
                register_number=register_number,
                is_valid=False,
                error_message=f"Student {register_number} has no registered email address.",
            )

        # Validate email syntax
        validate_email(email)

        return ResolvedRecipient(
            user=student_user,
            email=email,
            student_name=student_name,
            register_number=register_number,
            is_valid=True,
        )

    except ValidationError:
        logger.warning("Invalid recipient email syntax '%s' for student %s", email, register_number)
        return ResolvedRecipient(
            user=student_user,
            email=email,
            student_name=student_name,
            register_number=register_number,
            is_valid=False,
            error_message=f"Invalid email address '{email}' for student {register_number}.",
        )
    except Exception:
        logger.exception(
            "Error resolving recipient for request %s.",
            getattr(request_obj, "id", None),
        )
        return ResolvedRecipient(
            user=None,
            email="",
            student_name="",
            register_number="",
            is_valid=False,
            error_message="Unexpected error resolving the student recipient.",
        )


def resolve_test_recipient(recipient_email: str, admin_user=None) -> ResolvedRecipient:
    """Validate and resolve a test email recipient."""
    clean_email = (recipient_email or "").strip()
    if not clean_email:
        return ResolvedRecipient(
            user=admin_user,
            email="",
            student_name="Test Student",
            register_number="TEST001",
            is_valid=False,
            error_message="Test recipient email cannot be empty.",
        )

    try:
        validate_email(clean_email)
        return ResolvedRecipient(
            user=admin_user,
            email=clean_email,
            student_name="Test Student",
            register_number="TEST001",
            is_valid=True,
        )
    except ValidationError:
        return ResolvedRecipient(
            user=admin_user,
            email=clean_email,
            student_name="Test Student",
            register_number="TEST001",
            is_valid=False,
            error_message=f"Invalid email address: '{clean_email}'.",
        )
