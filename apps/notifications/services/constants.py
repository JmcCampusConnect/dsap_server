"""
Central Registry of Notification Placeholders and Sample Context.
"""

SUPPORTED_PLACEHOLDERS = {
    "student_name": {
        "description": "Student's full registered name",
        "sample": "Mohamed Jainul Haneef M I",
        "required": False,
    },
    "register_number": {
        "description": "Student's college register number",
        "sample": "24MCA066",
        "required": False,
    },
    "request_number": {
        "description": "Unique service request tracking number",
        "sample": "REQ-2026-0001",
        "required": True,
    },
    "service_name": {
        "description": "Name of the requested service",
        "sample": "Transcript Certificate",
        "required": False,
    },
    "previous_status": {
        "description": "Application status before the current transition",
        "sample": "SUBMITTED",
        "required": False,
    },
    "new_status": {
        "description": "Application status after the current transition",
        "sample": "VERIFIED",
        "required": False,
    },
    "remarks": {
        "description": "Staff remarks, comments, or reason for return/rejection",
        "sample": "All required documents verified successfully.",
        "required": False,
    },
    "action_date": {
        "description": "Date and time of the event / workflow action",
        "sample": "2026-11-15 10:30 UTC",
        "required": False,
    },
    "portal_url": {
        "description": "Direct link to view request on the student portal",
        "sample": "http://localhost:5173/requests/my/1",
        "required": False,
    },
}


def get_sample_context() -> dict[str, str]:
    """Return dictionary of sample values for template preview and testing."""
    return {k: v["sample"] for k, v in SUPPORTED_PLACEHOLDERS.items()}
