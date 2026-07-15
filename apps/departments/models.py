from django.db import models

class ServiceDepartment(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=150)
    hod_user_id = models.ForeignKey('common.User', on_delete=models.RESTRICT, null=True, blank=True, db_column='hod_user_id')
    status = models.CharField(max_length=10, default='ACTIVE')

    class Meta:
        db_table = 'servicedepartment'


class AcademicDepartment(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=150)
    hod_user_id = models.ForeignKey('common.User', on_delete=models.RESTRICT, null=True, blank=True, db_column='hod_user_id')
    status = models.CharField(max_length=10, default='ACTIVE')

    class Meta:
        db_table = 'academicdepartment'
