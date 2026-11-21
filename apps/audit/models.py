from django.db import models


class AuditLog(models.Model):
    
    ACTION_CHOICES = [
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('ACTIVATE', 'Activate'),
        ('DEACTIVATE', 'Deactivate'),
        ('DELETE', 'Delete'),
        ('VIEW', 'View'),
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
        ('UPLOAD', 'Upload'),
        ('EXPORT', 'Export'),
        ('IMPORT', 'Import'),
        ('IMPERSONATE_START', 'Impersonate Start'),
        ('IMPERSONATE_END', 'Impersonate End'),
        ('IMPERSONATED_REQUEST', 'Impersonated Request'),
    ]

    app_label = models.CharField(max_length=100, blank=True, null=True)
    model_name = models.CharField(max_length=100, blank=True, null=True)
    object_id = models.CharField(max_length=100, blank=True, null=True)
    object_repr = models.CharField(max_length=200, blank=True)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    changes = models.JSONField(default=dict, blank=True)
    user_id = models.CharField(max_length=100, blank=True, null=True)
    user_name = models.CharField(max_length=200, blank=True, null=True)
    impersonator_id = models.CharField(max_length=100, blank=True, null=True)
    impersonator_name = models.CharField(max_length=200, blank=True, null=True)
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
    def log(cls, request, action, obj=None, object_repr='', changes=None, object_id=None, app_label='', model_name='', user=None, impersonator_id=None, impersonator_name=None):
        resolved_app_label = app_label or ''
        resolved_model_name = model_name or ''
        resolved_object_id = str(object_id) if object_id is not None else ''
        resolved_object_repr = object_repr or ''

        if obj:
            if hasattr(obj, '_meta'):
                if not resolved_app_label:
                    resolved_app_label = obj._meta.app_label
                if not resolved_model_name:
                    resolved_model_name = obj._meta.object_name

            if isinstance(obj, models.Model):
                if object_id is None and obj.pk is not None:
                    resolved_object_id = str(obj.pk)
                if not resolved_object_repr:
                    resolved_object_repr = str(obj)
            elif not resolved_object_repr and hasattr(obj, '_meta'):
                resolved_object_repr = f"Bulk {action.title()} {obj._meta.verbose_name_plural.title()}"

        audit_data = {
            'app_label': resolved_app_label,
            'model_name': resolved_model_name,
            'object_id': resolved_object_id,
            'object_repr': resolved_object_repr,
            'action': action,
            'changes': changes or {},
            'ip_address': cls._get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', '') if request else '',
            'request_path': request.path if request else '',
        }
        
        if user:
            audit_data['user_id'] = str(user.id)
            audit_data['user_name'] = user.username
        elif request and hasattr(request, 'user') and request.user.is_authenticated:
            audit_data['user_id'] = str(request.user.id)
            audit_data['user_name'] = request.user.username

        # Capture impersonation context from explicit args first, then from
        # token claims if present (actions performed during an impersonation).
        token = getattr(request, 'auth', None) if request else None
        payload = getattr(token, 'payload', {}) if token else {}
        if impersonator_id is not None or impersonator_name is not None:
            audit_data['impersonator_id'] = str(impersonator_id) if impersonator_id is not None else ''
            audit_data['impersonator_name'] = str(impersonator_name) if impersonator_name is not None else ''
        elif payload.get('is_impersonation'):
            audit_data['impersonator_id'] = str(payload.get('impersonator_id', ''))
            audit_data['impersonator_name'] = str(payload.get('impersonator_name', ''))

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