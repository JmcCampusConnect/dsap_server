"""
Shared API exception types.

Every subclass sets ``detail`` to a dict, so DRF's default exception
handler emits it verbatim (no extra ``{"detail": ...}`` wrapper).
"""

from rest_framework import status
from rest_framework.exceptions import APIException


class FieldNotEditableError(APIException):
    """400 — caller sent one or more fields outside the editable allow-list."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "FIELD_NOT_EDITABLE"

    def __init__(self, fields):
        fields = list(fields)
        super().__init__(
            detail={
                "error": "FIELD_NOT_EDITABLE",
                "message": f"The following fields are not editable: {', '.join(fields)}.",
                "fields": fields,
            }
        )


class ValidationFailedError(APIException):
    """400 — request body failed validation (bad mobile, email, empty body)."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "VALIDATION_ERROR"

    def __init__(self, details):
        super().__init__(
            detail={
                "error": "VALIDATION_ERROR",
                "details": details,
            }
        )


class EmailExistsError(APIException):
    """409 — email is already owned by another user."""

    status_code = status.HTTP_409_CONFLICT
    default_code = "EMAIL_EXISTS"

    def __init__(self):
        super().__init__(
            detail={
                "error": "EMAIL_EXISTS",
                "message": "A user with this email already exists.",
            }
        )


class ProfileNotFoundError(APIException):
    """404 — STUDENT user has no linked Student record."""

    status_code = status.HTTP_404_NOT_FOUND
    default_code = "PROFILE_NOT_FOUND"

    def __init__(self):
        super().__init__(
            detail={
                "error": "PROFILE_NOT_FOUND",
                "message": "Student record is missing for this user.",
            }
        )