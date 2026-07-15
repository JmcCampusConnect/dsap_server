from django.db import models

class Service(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    service_department_id = models.ForeignKey('departments.ServiceDepartment', on_delete=models.RESTRICT, db_column='service_department_id')
    base_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    sla_days = models.SmallIntegerField(default=7)
    status = models.CharField(max_length=10, default='ENABLED')

    class Meta:
        db_table = 'service'


class ServiceField(models.Model):
    service_id = models.ForeignKey('services.Service', on_delete=models.CASCADE, db_column='service_id')
    field_label = models.CharField(max_length=150)
    field_type = models.CharField(max_length=20)
    is_required = models.BooleanField(default=False)
    display_order = models.SmallIntegerField(default=0)
    options_json = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = 'servicefield'


class ServiceDocument(models.Model):
    service_id = models.ForeignKey('services.Service', on_delete=models.CASCADE, db_column='service_id')
    document_name = models.CharField(max_length=150)
    is_mandatory = models.BooleanField(default=True)

    class Meta:
        db_table = 'servicedocument'
