from django.db import models
from .fields import EncryptedTextField


class Student(models.Model):
    
    class StreamChoices(models.TextChoices):
        SFM = 'SFM', 'SFM'
        SFW = 'SFW', 'SFW'
        AIDED = 'AIDED', 'Aided'

    id = models.BigAutoField(primary_key=True)

    register_number = models.CharField(
        max_length=30,
        unique=True
    )

    name = models.CharField(
        max_length=100
    )

    dob = models.DateField(
        null=True,
        blank=True
    )

    user_id = models.OneToOneField(
        'accounts.User',
        on_delete=models.RESTRICT,
        db_column='user_id'
    )

    academic_department_id = models.ForeignKey(
        'departments.AcademicDepartment',
        on_delete=models.RESTRICT,
        db_column='academic_department_id'
    )

    year_of_admission = models.CharField(max_length=9)

    section = models.CharField(
        max_length=10,
        null=True,
        blank=True
    )

    stream = models.CharField(
        max_length=10,
        choices=StreamChoices.choices,
        default=StreamChoices.SFM
    )
    
    mobile_number = models.CharField(max_length=15)
    religion = models.CharField(max_length=50, null=True, blank=True)
    aadhaar_number = EncryptedTextField(null=True, blank=True)

    parent_name = models.CharField(max_length=100, null=True, blank=True)
    parent_mobile = models.CharField(max_length=15, null=True, blank=True)

    status = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'student'

    def __str__(self):
        return self.register_number
