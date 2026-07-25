MENU_ACCESS_CONFIG = {
    'dashboard': [
        'SYSTEM_ADMIN',
        'SERVICE_DEPT_ADMIN',
        'SERVICE_DEPT_STAFF',
        'SUBJECT_TEACHING_STAFF',
        'STUDENT'
    ],
    'users': [
        'SYSTEM_ADMIN'
    ],
    'students': [
        'SYSTEM_ADMIN',
        'SERVICE_DEPT_ADMIN'
    ],
    'staff': [
        'SYSTEM_ADMIN',
        'SERVICE_DEPT_ADMIN'
    ],
    'subjects': [
        'SYSTEM_ADMIN',
        'SUBJECT_TEACHING_STAFF'
    ],
    'attendance': [
        'SYSTEM_ADMIN',
        'SERVICE_DEPT_ADMIN',
        'SERVICE_DEPT_STAFF',
        'SUBJECT_TEACHING_STAFF'
    ],
    'results': [
        'SYSTEM_ADMIN',
        'SERVICE_DEPT_ADMIN',
        'SUBJECT_TEACHING_STAFF',
        'STUDENT'
    ],
    'service-departments': [
        'SYSTEM_ADMIN',
        'SERVICE_DEPT_ADMIN'
    ],
    'academic-departments': [
        'SYSTEM_ADMIN',
        'SUBJECT_TEACHING_STAFF'
    ],
    'reports': [
        'SYSTEM_ADMIN',
        'SERVICE_DEPT_ADMIN',
        'SERVICE_DEPT_STAFF'
    ],
    'settings': [
        'SYSTEM_ADMIN'
    ],
    'profile': [
        'SYSTEM_ADMIN',
        'SERVICE_DEPT_ADMIN',
        'SERVICE_DEPT_STAFF',
        'SUBJECT_TEACHING_STAFF',
        'STUDENT'
    ]
}

def has_menu_access(role_name, menu_key):
    """Check if a role has access to a specific menu"""
    if not role_name or not menu_key:
        return False
    allowed_roles = MENU_ACCESS_CONFIG.get(menu_key, [])
    return role_name in allowed_roles

def get_accessible_menus(role_name):
    """Get all menus accessible by a specific role"""
    if not role_name:
        return []
    return [menu for menu, roles in MENU_ACCESS_CONFIG.items() if role_name in roles]