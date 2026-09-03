from django.contrib.auth.hashers import make_password
from django.db import transaction
from rest_framework import serializers

from apps.accounts.models import Role, User
from apps.departments.models import AcademicDepartment

from .models import Student


class StudentSerializer(serializers.ModelSerializer):
    academic_department_id = serializers.PrimaryKeyRelatedField(
        queryset=AcademicDepartment.objects.all(),
        required=False,
        allow_null=True,
    )
    dob = serializers.DateField(
        required=False,
        allow_null=True,
        input_formats=['%d-%m-%Y'],
        format='%d-%m-%Y',
    )
    user_id = serializers.IntegerField(source='user_id_id', read_only=True)
    academic_department_name = serializers.SerializerMethodField()
    email = serializers.EmailField(required=False, allow_null=True, write_only=True)
    role_id = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.all(),
        required=False,
        allow_null=True,
        write_only=True,
    )

    class Meta:
        model = Student
        fields = [
            'id',
            'register_number',
            'name',
            'user_id',
            'academic_department_id',
            'academic_department_name',
            'year_of_admission',
            'dob',
            'section',
            'stream',
            'mobile_number',
            'status',
            'email',
            'role_id',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'user_id',
            'academic_department_name',
            'created_at',
            'updated_at',
        ]

    def get_academic_department_name(self, obj):
        department = getattr(obj, 'academic_department_id', None)
        if not department:
            return None
        parts = [department.code, department.degree, department.branch]
        return ' - '.join(part for part in parts if part)

    def _get_student_role(self, role_obj):
        if role_obj is not None:
            return role_obj
        role = Role.objects.filter(name='STUDENT').first()
        if not role:
            raise serializers.ValidationError({'role_id': 'STUDENT role does not exist.'})
        return role

    @staticmethod
    def _extract_department_code(register_number):
        value = str(register_number or '').strip()
        if len(value) < 5:
            return None
        return value[2:5].strip().upper() or None

    def _get_department_from_register_number(self, register_number):
        department_code = self._extract_department_code(register_number)
        if not department_code:
            raise serializers.ValidationError({'register_number': 'Department not found.'})

        department = AcademicDepartment.objects.filter(code__iexact=department_code).first()
        if not department:
            raise serializers.ValidationError({'register_number': 'Department not found.'})

        return department

    def validate_stream(self, value):
        normalized = str(value).strip()
        if not normalized:
            raise serializers.ValidationError('Stream cannot be empty.')

        lookup = normalized.upper()
        if lookup == 'AIDED':
            return 'AIDED'
        if lookup in {'SFM', 'SFW'}:
            return lookup

        raise serializers.ValidationError('Stream must be one of SFM, SFW, or Aided.')

    def validate_register_number(self, value):
        value = str(value).strip()
        if not value:
            raise serializers.ValidationError('Register number cannot be empty.')
        queryset = Student.objects.filter(register_number__iexact=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError('A student with this register number already exists.')
        return value

    def validate_email(self, value):
        if value in (None, ''):
            return None

        email = str(value).strip()
        if not email:
            return None

        queryset = User.objects.filter(email__iexact=email)
        if self.instance and self.instance.user_id_id:
            queryset = queryset.exclude(pk=self.instance.user_id_id)
        if queryset.exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return email

    def validate_name(self, value):
        value = str(value).strip()
        if not value:
            raise serializers.ValidationError('Name cannot be empty.')
        return value

    def validate_year_of_admission(self, value):
        value = str(value).strip()
        if not value:
            raise serializers.ValidationError('Year of admission cannot be empty.')
        return value

    def validate_mobile_number(self, value):
        value = str(value).strip()
        if not value:
            raise serializers.ValidationError('Mobile number cannot be empty.')
        return value

    @transaction.atomic
    def create(self, validated_data):
        register_number = validated_data['register_number']
        dob = validated_data.get('dob')
        if not dob:
            raise serializers.ValidationError({'dob': 'Date of birth is required to create the student login.'})

        department = self._get_department_from_register_number(register_number)
        role = self._get_student_role(validated_data.pop('role_id', None))
        validated_data.pop('academic_department_id', None)
        email = validated_data.pop('email', None)

        user = User.objects.create(
            username=register_number,
            email=email,
            password_hash=make_password(dob.isoformat()),
            role_id=role,
            academic_department_id=department,
            is_active=bool(validated_data.get('status', True)),
        )

        student = Student.objects.create(
            user_id=user,
            academic_department_id=department,
            **validated_data,
        )
        return student

    @transaction.atomic
    def update(self, instance, validated_data):
        register_number = validated_data.get('register_number', instance.register_number)
        dob = validated_data.get('dob', instance.dob)
        email = validated_data.pop('email', None)
        role = self._get_student_role(validated_data.pop('role_id', None))
        department = self._get_department_from_register_number(register_number)
        validated_data.pop('academic_department_id', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.academic_department_id = department

        if instance.user_id:
            instance.user_id.username = register_number
            if email is not None:
                instance.user_id.email = email
            instance.user_id.password_hash = make_password(dob.isoformat()) if dob else instance.user_id.password_hash
            instance.user_id.role_id = role
            instance.user_id.academic_department_id = department
            instance.user_id.is_active = bool(instance.status)
            instance.user_id.save()

        instance.save()
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if data.get('stream') and str(data['stream']).upper() == 'AIDED':
            data['stream'] = 'Aided'
        return data
