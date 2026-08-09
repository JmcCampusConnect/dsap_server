# apps/accounts/role_constants.py
from typing import List

class Roles:
    """Single source of truth for role names. Use everywhere, never hardcode strings."""
    SYSTEM_ADMIN = "SYSTEM_ADMIN"
    SERVICE_DEPT_ADMIN = "SERVICE_DEPT_ADMIN"
    SERVICE_DEPT_STAFF = "SERVICE_DEPT_STAFF"
    STUDENT = "STUDENT"
    SUBJECT_TEACHING_STAFF = "SUBJECT_TEACHING_STAFF"

    @classmethod
    def all(cls) -> List[str]:
        return [
            cls.SYSTEM_ADMIN,
            cls.SERVICE_DEPT_ADMIN,
            cls.SERVICE_DEPT_STAFF,
            cls.STUDENT,
            cls.SUBJECT_TEACHING_STAFF,
        ]

    @classmethod
    def department_scoped(cls) -> List[str]:
        return [cls.SERVICE_DEPT_ADMIN, cls.SERVICE_DEPT_STAFF]

# For Django choices if needed
ROLE_CHOICES = [(r, r) for r in Roles.all()]

# -------------------------------------------------
# Menu Key -> Allowed Roles (Backend + Frontend SSOT)
# Based on Role_Based_Menu_Structure.docx Section 9 + Frontend_Tasks example
# -------------------------------------------------
MENU_ACCESS_CONFIG = {
    # Common - all authenticated
    "dashboard": Roles.all(),
    "notifications": Roles.all(),
    "profile": Roles.all(),

    # Old keys (keep for backward compat with your current frontend)
    "users": [Roles.SYSTEM_ADMIN],
    "students": [Roles.SYSTEM_ADMIN, Roles.SERVICE_DEPT_ADMIN],
    "staff": [Roles.SYSTEM_ADMIN, Roles.SERVICE_DEPT_ADMIN],
    "service-departments": [Roles.SYSTEM_ADMIN, Roles.SERVICE_DEPT_ADMIN],
    "academic-departments": [Roles.SYSTEM_ADMIN],
    "reports": [Roles.SYSTEM_ADMIN, Roles.SERVICE_DEPT_ADMIN, Roles.SERVICE_DEPT_STAFF],
    "settings": [Roles.SYSTEM_ADMIN],
    "subjects": [Roles.SYSTEM_ADMIN, Roles.SUBJECT_TEACHING_STAFF],
    "attendance": [Roles.SYSTEM_ADMIN, Roles.SERVICE_DEPT_ADMIN, Roles.SERVICE_DEPT_STAFF, Roles.SUBJECT_TEACHING_STAFF],
    "results": [Roles.SYSTEM_ADMIN, Roles.SERVICE_DEPT_ADMIN, Roles.SUBJECT_TEACHING_STAFF, Roles.STUDENT],

    # New canonical keys from Doc Section 9 (use these going forward)
    "service_directory": [Roles.STUDENT],
    "my_requests": [Roles.STUDENT],
    "payment_history": [Roles.STUDENT],

    "pending_requests": [Roles.SYSTEM_ADMIN, Roles.SERVICE_DEPT_ADMIN, Roles.SERVICE_DEPT_STAFF],
    "approved_requests": [Roles.SYSTEM_ADMIN, Roles.SERVICE_DEPT_ADMIN, Roles.SERVICE_DEPT_STAFF],
    "rejected_requests": [Roles.SYSTEM_ADMIN, Roles.SERVICE_DEPT_ADMIN, Roles.SERVICE_DEPT_STAFF],
    "completed_requests": [Roles.SYSTEM_ADMIN, Roles.SERVICE_DEPT_ADMIN, Roles.SERVICE_DEPT_STAFF],

    "services": [Roles.SYSTEM_ADMIN, Roles.SERVICE_DEPT_ADMIN],
    "my_department": [Roles.SERVICE_DEPT_ADMIN],

    # System Admin only - distinct from scoped list
    "service_departments_full": [Roles.SYSTEM_ADMIN],
    "academic_departments_full": [Roles.SYSTEM_ADMIN],
    "notification_templates": [Roles.SYSTEM_ADMIN],
    "audit_log": [Roles.SYSTEM_ADMIN],
    "system_settings": [Roles.SYSTEM_ADMIN],
}

def has_menu_access(role_name: str, menu_key: str) -> bool:
    if not role_name or not menu_key:
        return False
    return role_name in MENU_ACCESS_CONFIG.get(menu_key, [])

def get_accessible_menus(role_name: str) -> List[str]:
    if not role_name:
        return []
    return [menu for menu, roles in MENU_ACCESS_CONFIG.items() if role_name in roles]

# Capability mapping for future navConfig.js style (request.submit etc)
CAPABILITY_MAP = {
    "request.submit": [Roles.STUDENT],
    "request.track_own": [Roles.STUDENT],
    "request.review": [Roles.SYSTEM_ADMIN, Roles.SERVICE_DEPT_ADMIN, Roles.SERVICE_DEPT_STAFF],
    "service.manage": [Roles.SYSTEM_ADMIN, Roles.SERVICE_DEPT_ADMIN],
    "service_department.manage": [Roles.SERVICE_DEPT_ADMIN],
    "service_department.manage_all": [Roles.SYSTEM_ADMIN],
    "academic_department.manage": [Roles.SYSTEM_ADMIN],
    "user.manage": [Roles.SYSTEM_ADMIN, Roles.SERVICE_DEPT_ADMIN],
    "student.manage": [Roles.SYSTEM_ADMIN],
    "notification_template.manage": [Roles.SYSTEM_ADMIN],
    "audit_log.view": [Roles.SYSTEM_ADMIN],
    "system_settings.manage": [Roles.SYSTEM_ADMIN],
    "report.view": [Roles.SYSTEM_ADMIN, Roles.SERVICE_DEPT_ADMIN, Roles.SERVICE_DEPT_STAFF],
}