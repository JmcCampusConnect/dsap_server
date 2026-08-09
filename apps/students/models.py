import hashlib

from django.db import models

from .fields import EncryptedTextField


class Student(models.Model):

    class StreamChoices(models.TextChoices):
        SFM = 'SFM', 'SFM'
        SFW = 'SFW', 'SFW'
        AIDED = 'Aided', 'Aided'

    class StatusChoices(models.TextChoices):
        ACTIVE = 'active', 'Active'
        INACTIVE = 'inactive', 'Inactive'

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
        null=True,
        blank=True,
        db_column='academic_department_id'
    )

    batch_year = models.CharField(max_length=9)

    date_of_birth = models.DateField(blank=True, null=True)

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

    religion = models.CharField(max_length=50, blank=True, null=True)
    aadhar_no = EncryptedTextField(blank=True, null=True)
    aadhar_no_hash = models.CharField(max_length=64, unique=True, blank=True, null=True, db_index=True)
    address_line1 = models.CharField(max_length=255, blank=True, null=True)
    address_line2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    district = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    pincode = models.CharField(max_length=10, blank=True, null=True)
    father_name = models.CharField(max_length=150, blank=True, null=True)
    mother_name = models.CharField(max_length=150, blank=True, null=True)
    guardian_name = models.CharField(max_length=150, blank=True, null=True)
    parent_mobile_number = models.CharField(max_length=15, blank=True, null=True)
    parent_email = models.EmailField(max_length=150, blank=True, null=True)

    status = models.CharField(
        max_length=10,
        choices=StatusChoices.choices,
        default=StatusChoices.ACTIVE
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'student'

    def __str__(self):
        return self.register_number

    @property
    def name(self):
        return self.register_number

    @staticmethod
    def hash_aadhar(value: str | None) -> str | None:
        if value in (None, ''):
            return None
        normalized = str(value).strip()
        if not normalized:
            return None
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()
