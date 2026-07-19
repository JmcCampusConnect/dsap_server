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
        'common.Role',
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

    academic_department_id = models.ForeignKey(
        'departments.AcademicDepartment',
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        db_column='academic_department_id'
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
        """Required by Django's authentication system."""
        return True

    @property
    def is_anonymous(self):
        """Required by Django's authentication system."""
        return False
    
    @property
    def role(self):
        """Alias for role_id to match the expected attribute name."""
        return self.role_id

    def check_password(self, raw_password):
        """Check the password against the stored hash."""
        from django.contrib.auth.hashers import check_password
        return check_password(raw_password, self.password_hash)

    def set_password(self, raw_password):
        """Hash and set the password (not used by seeder, but good practice)."""
        from django.contrib.auth.hashers import make_password
        self.password_hash = make_password(raw_password)
        self._password = raw_password

    def get_username(self):
        """Return the username (used by some auth internals)."""
        return self.username

    # Optional: if you want to support the admin interface, add:
    @property
    def is_staff(self):
        return self.role_id.name == 'SYSTEM_ADMIN' if self.role_id else False

    @property
    def is_superuser(self):
        return self.role_id.name == 'SYSTEM_ADMIN' if self.role_id else False

    def has_perm(self, perm, obj=None):
        return True   # implement custom permission logic if needed

    def has_module_perms(self, app_label):
        return True
    

    class Meta:
        db_table = 'user'

    def __str__(self):
        return self.username


class AuditLog(models.Model):

    ACTION_CHOICES = [
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('VIEW', 'View'),
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
        ('UPLOAD', 'Upload'),
        ('EXPORT', 'Export'),
    ]

    app_label = models.CharField(max_length=100, db_index=True, blank=True, null=True)
    model_name = models.CharField(max_length=100, blank=True, null=True)
    object_id = models.CharField(max_length=100, blank=True, null=True)
    object_repr = models.CharField(max_length=200, blank=True)
    
    action = models.CharField(max_length=10, choices=ACTION_CHOICES, db_index=True)
    changes = models.JSONField(default=dict, blank=True)
    
    user_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    user_name = models.CharField(max_length=200, blank=True)
    
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    request_path = models.CharField(max_length=500, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'audit_log'
        indexes = [
            models.Index(fields=['app_label', 'model_name', 'object_id']),
            models.Index(fields=['action', 'created_at']),
            models.Index(fields=['user_id', 'created_at']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.action} - {self.object_repr} - {self.created_at}"

    @classmethod
    def log(cls, request, action, obj=None, changes=None, object_repr=None):
        audit_data = {
            'action': action,
            'changes': changes or {},
            'ip_address': cls._get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'request_path': request.path,
        }
        if request.user.is_authenticated:
            audit_data['user_id'] = str(request.user.id)
            audit_data['user_name'] = request.user.username
        if obj:
            audit_data['app_label'] = obj._meta.app_label
            audit_data['model_name'] = obj.__class__.__name__
            audit_data['object_id'] = str(obj.pk)
            audit_data['object_repr'] = object_repr or str(obj)
        return cls.objects.create(**audit_data)

    @staticmethod
    def _get_client_ip(request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
