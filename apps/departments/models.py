from django.db import models

class ServiceDepartment(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=150)
    hod_user_id = models.ForeignKey('common.User', on_delete=models.RESTRICT, null=True, blank=True, db_column='hod_user_id')
    status = models.CharField(max_length=10, default='ACTIVE')

    class Meta:
        db_table = 'servicedepartment'


class AcademicDepartment(models.Model):
    TYPE_CHOICES = [
        ('UG', 'UG'),
        ('PG', 'PG'),
    ]

    CATEGORY_CHOICES = [
        ('Arts', 'Arts'),
        ('Science', 'Science'),
    ]

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=150)
    degree = models.CharField(max_length=100)
    branch = models.CharField(max_length=100)
    type = models.CharField(max_length=2, choices=TYPE_CHOICES)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    hod_user_id = models.ForeignKey(
        'common.User',
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        db_column='hod_user_id'
    )
    status = models.CharField(max_length=10, default='ACTIVE')

    class Meta:
        db_table = 'academicdepartment'

    def __str__(self):
        return f"{self.code} - {self.name}"
