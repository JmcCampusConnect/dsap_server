from django.db import models


class SystemSetting(models.Model):
    key = models.CharField(max_length=255, unique=True)
    value = models.JSONField(default=dict, blank=True, null=True)

    class Meta:
        db_table = 'system_setting'

    def __str__(self):
        return self.key

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

    app_label = models.CharField(max_length=100, blank=True, null=True)
    model_name = models.CharField(max_length=100, blank=True, null=True)
    object_id = models.CharField(max_length=100, blank=True, null=True)
    object_repr = models.CharField(max_length=200, blank=True)
    
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    changes = models.JSONField(default=dict, blank=True)
    
    user_id = models.CharField(max_length=100, blank=True, null=True)
    user_name = models.CharField(max_length=200, blank=True, null=True)
    
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    request_path = models.CharField(max_length=500, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'audit_log'
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['model_name']),
            models.Index(fields=['user_id']),
            models.Index(fields=['action']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.action} - {self.object_repr} - {self.created_at}"

    @classmethod
    def log(cls, request, action, obj, object_repr='', changes=None):
        app_label = ''
        model_name = ''
        object_id = ''
        
        if obj:
            app_label = obj._meta.app_label
            model_name = obj.__class__.__name__
            object_id = str(obj.pk)
            if not object_repr:
                object_repr = str(obj)
                
        audit_data = {
            'app_label': app_label,
            'model_name': model_name,
            'object_id': object_id,
            'object_repr': object_repr,
            'action': action,
            'changes': changes or {},
            'ip_address': cls._get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'request_path': request.path,
        }
        
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            audit_data['user_id'] = str(request.user.id)
            audit_data['user_name'] = request.user.username
            
        return cls.objects.create(**audit_data)

    @staticmethod
    def _get_client_ip(request):
        if not request:
            return None
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
