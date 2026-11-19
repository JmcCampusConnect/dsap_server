from django.db import models


class Role(models.Model):

    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=50, unique=True, null=False)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "role"

    def __str__(self):
        return self.name


class User(models.Model):

    id = models.BigAutoField(primary_key=True)
    username = models.CharField(max_length=100,unique=True)

    email = models.EmailField(
        max_length=150,
        unique=True,
        null=True,
        blank=True
    )

    password_hash = models.CharField(max_length=255)

    role_id = models.ForeignKey(
        'accounts.Role',
        on_delete=models.RESTRICT,
        db_column='role_id'
    )

    service_department_id = models.ForeignKey(
        'departments.ServiceDepartment',
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        db_column='service_department_id'
    )

    is_active = models.BooleanField(default=True)

    last_login = models.DateTimeField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']
    
    @property
    def is_authenticated(self):
        return True
    
    @property
    def is_anonymous(self):
        return False
    
    # --- RBAC helpers (NEW) ---
    @property
    def role_name(self) -> str | None:
        return getattr(self.role_id, 'name', None) if self.role_id else None
    
    @property
    def service_department(self):
        return self.service_department_id
    
    def has_role(self, role_name: str) -> bool:
        return self.role_name == role_name
    
    def has_any_role(self, roles: list[str]) -> bool:
        return self.role_name in roles
    
    def is_system_admin(self) -> bool:
        from.role_constants import Roles
        return self.has_role(Roles.SYSTEM_ADMIN)

    class Meta:
        db_table = 'user'

    def __str__(self):
        return self.username


class ImpersonationSession(models.Model):
    """
    Tracks active and historical impersonation sessions started by SYSTEM_ADMIN users.

    One row is created when impersonation starts (is_active=True) and closed
    (is_active=False, ended_at=now) when the admin exits, the token expires, or
    the session is superseded by a new one.
    """

    admin_user = models.ForeignKey(
        'accounts.User',
        on_delete=models.RESTRICT,
        related_name='impersonation_sessions_started',
        db_column='admin_user_id',
    )
    target_user = models.ForeignKey(
        'accounts.User',
        on_delete=models.RESTRICT,
        related_name='impersonation_sessions_received',
        db_column='target_user_id',
    )
    reason = models.TextField()
    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'impersonation_session'
        indexes = [
            models.Index(fields=['admin_user', 'is_active']),
            models.Index(fields=['target_user', 'is_active']),
        ]

    def __str__(self):
        return f"ImpersonationSession(admin={self.admin_user_id}, target={self.target_user_id}, active={self.is_active})"
    
