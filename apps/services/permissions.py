"""
Service app permissions.

Re-exports the centralized RBAC classes from apps.accounts.permissions
so existing imports (`from apps.services.permissions import IsSystemAdmin`)
keep working without duplicating or diverging permission logic.
"""
from apps.accounts.permissions import (  # noqa: F401
    IsSystemAdmin,
    IsServiceDeptAdmin,
    IsServiceDeptStaff,
    IsOwnServiceDepartment,
    IsOwnAcademicDepartment,
)