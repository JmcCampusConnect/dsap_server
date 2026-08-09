# apps/departments/permissions.py
# Re‑export the reusable permission classes from accounts
from apps.accounts.permissions import (
    IsSystemAdmin,
    IsServiceDeptAdmin,
    IsServiceDeptStaff,
    IsOwnServiceDepartment,
    IsSelfStudent,
    IsSelfOrSystemAdmin,
)

# You can also add department‑specific aliases if desired
IsServiceDepartmentAdmin = IsServiceDeptAdmin