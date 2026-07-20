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
        'accounts.Role',
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
