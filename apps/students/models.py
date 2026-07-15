from django.db import models

class Student(models.Model):
    register_number = models.CharField(max_length=30, unique=True)
    user_id = models.OneToOneField('common.User', on_delete=models.RESTRICT, db_column='user_id')
    academic_department_id = models.ForeignKey('departments.AcademicDepartment', on_delete=models.RESTRICT, db_column='academic_department_id')
    batch_year = models.CharField(max_length=9)
    mobile_number = models.CharField(max_length=15)
    id_card_barcode = models.CharField(max_length=50, unique=True, null=True, blank=True)
    status = models.CharField(max_length=10, default='ACTIVE')

    class Meta:
        db_table = 'student'
