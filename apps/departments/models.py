from django.db import models


class ServiceDepartment(models.Model):
    
    id = models.BigAutoField(primary_key=True)
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=150)
    hod_user_id = models.ForeignKey(
        # 'common.User',
        'accounts.User',
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        db_column='hod_user_id'
    )
    status = models.CharField(max_length=10, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'service_department' 

    def __str__(self):
        return f"{self.code} - {self.name}"


class AcademicDepartment(models.Model):
    
    TYPE_CHOICES = (
        ('UG', 'Undergraduate'),
        ('PG', 'Postgraduate'),
    )
    
    CATEGORY_CHOICES = (
        ('ARTS', 'Arts'),
        ('SCIENCE', 'Science'),
    )

    STREAM_CHOICES = (
        ('SFM', 'SFM'),
        ('SFW', 'SFW'),
        ('Aided', 'Aided'),
    )

    id = models.BigAutoField(primary_key=True)
    code = models.CharField(max_length=20)
    stream = models.CharField(max_length=10, choices=STREAM_CHOICES, default='SFM')
    degree = models.CharField(max_length=50)
    branch = models.CharField(max_length=100)
    type = models.CharField(max_length=100)
    category = models.CharField(max_length=100)
    status = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'academic_department'
        unique_together = ('code', 'stream')

    def __str__(self):
        return f"{self.code} ({self.stream}) - {self.degree}"
