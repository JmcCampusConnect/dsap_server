from django.db import models


class Student(models.Model):
    
    id = models.BigAutoField(primary_key=True)

    register_number = models.CharField(
        max_length=30,
        unique=True
    )

    user_id = models.OneToOneField(
        # 'common.User',
        'accounts.User',
        on_delete=models.RESTRICT,
        db_column='user_id'
    )

    academic_department_id = models.ForeignKey(
        'departments.AcademicDepartment',
        on_delete=models.RESTRICT,
        db_column='academic_department_id'
    )

    batch_year = models.CharField(max_length=9)

    section = models.CharField(
        max_length=10,
        null=True,
        blank=True
    )

    stream = models.CharField(max_length=10)

    mobile_number = models.CharField(max_length=15)

    religion = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )

    aadhar_no = models.CharField(
        max_length=12,
        unique=True,
        null=True,
        blank=True
    )

    door_no = models.CharField(
        max_length=20,
        null=True,
        blank=True
    )

    area_name = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    district = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    state = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    pincode = models.CharField(
        max_length=10,
        null=True,
        blank=True
    )

    parent_name = models.CharField(
        max_length=150,
        null=True,
        blank=True
    )

    parent_number = models.CharField(
        max_length=15,
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=10,
        default='ACTIVE'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'student'

    def __str__(self):
        return self.register_number