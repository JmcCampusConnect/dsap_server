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

    class Meta:
        db_table = 'user'

    def __str__(self):
        return self.username


class SystemSetting(models.Model):
    key = models.CharField(max_length=255, unique=True)
    value = models.JSONField(default=dict, blank=True, null=True)

    class Meta:
        db_table = 'system_setting'

    def __str__(self):
        return self.key

    @classmethod
    def get_setting(cls, key, default=None):
        try:
            setting = cls.objects.get(key=key)
            return setting.value
        except cls.DoesNotExist:
            return default


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
