import hashlib

from django.contrib.auth.hashers import make_password
from django.db import transaction
from rest_framework import serializers

from apps.accounts.models import Role, User
from apps.departments.models import AcademicDepartment
from .models import Student


def _normalize_stream(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    if normalized.upper() == 'AIDED':
        return 'Aided'
    allowed = {'SFM', 'SFW', 'Aided'}
    if normalized not in allowed:
        raise serializers.ValidationError('Stream must be one of: SFM, SFW, Aided.')
    return normalized


def _normalize_status(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if not normalized:
        return None
    allowed = {'active', 'inactive'}
    if normalized not in allowed:
        raise serializers.ValidationError('Status must be either active or inactive.')
    return normalized


class StudentSerializer(serializers.ModelSerializer):
    academic_department_id = serializers.PrimaryKeyRelatedField(
        queryset=AcademicDepartment.objects.all(),
        required=False,
        allow_null=True
    )
    date_of_birth = serializers.DateField(
        required=False,
        allow_null=True,
        input_formats=['%d-%m-%Y'],
        format='%d-%m-%Y',
    )
    user_id = serializers.IntegerField(source='user_id_id', read_only=True)
    name = serializers.SerializerMethodField()
    academic_department_name = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = [
            'id',
            'register_number',
            'user_id',
            'academic_department_id',
            'academic_department_name',
            'name',
            'batch_year',
            'date_of_birth',
            'section',
            'stream',
            'mobile_number',
            'religion',
            'aadhar_no',
            'address_line1',
            'address_line2',
            'city',
            'district',
            'state',
            'pincode',
            'father_name',
            'mother_name',
            'guardian_name',
            'parent_mobile_number',
            'parent_email',
            'status',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'user_id',
            'academic_department_name',
            'name',
            'created_at',
            'updated_at',
        ]

    def get_name(self, obj):
        return obj.name

    def get_academic_department_name(self, obj):
        department = getattr(obj, 'academic_department_id', None)
        if not department:
            return None
        parts = [department.code, department.degree, department.branch]
        return ' - '.join(part for part in parts if part)

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

    def validate_batch_year(self, value):
        value = str(value).strip()
        if not value:
            raise serializers.ValidationError('Batch year cannot be empty.')
        return value

    def validate_date_of_birth(self, value):
        return value

    def validate_mobile_number(self, value):
        value = str(value).strip()
        if not value:
            raise serializers.ValidationError('Mobile number cannot be empty.')
        return value

    def validate_stream(self, value):
        return _normalize_stream(value)

    def validate_status(self, value):
        return _normalize_status(value)

    def validate_aadhar_no(self, value):
        if value in (None, ''):
            return None
        normalized = str(value).strip()
        if normalized and (not normalized.isdigit() or len(normalized) != 12):
            raise serializers.ValidationError('Aadhar number must contain exactly 12 digits.')
        aadhar_hash = hashlib.sha256(normalized.encode('utf-8')).hexdigest()
        queryset = Student.objects.filter(aadhar_no_hash=aadhar_hash)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError('A student with this Aadhar number already exists.')
        return normalized or None

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs.get('status') is None:
            attrs['status'] = Student.StatusChoices.ACTIVE
        if attrs.get('stream') is None:
            attrs['stream'] = Student.StreamChoices.SFM
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if data.get('status'):
            data['status'] = str(data['status']).lower()
        if data.get('stream') and str(data['stream']).upper() == 'AIDED':
            data['stream'] = 'Aided'
        return data

    def _get_student_role(self):
        role = Role.objects.filter(name='STUDENT').first()
        if not role:
            raise serializers.ValidationError({'role': 'STUDENT role does not exist.'})
        return role

    @transaction.atomic
    def create(self, validated_data):
        register_number = validated_data['register_number']
        status_value = str(validated_data.get('status', Student.StatusChoices.ACTIVE)).lower()
        aadhar_no = validated_data.get('aadhar_no')
        validated_data['aadhar_no_hash'] = Student.hash_aadhar(aadhar_no)
        role = self._get_student_role()

        user = User.objects.create(
            username=register_number,
            email=None,
            password_hash=make_password(register_number),
            role_id=role,
            is_active=status_value == Student.StatusChoices.ACTIVE,
        )

        student = Student.objects.create(
            user_id=user,
            **validated_data,
        )
        return student

    @transaction.atomic
    def update(self, instance, validated_data):
        new_register_number = validated_data.get('register_number', instance.register_number)
        new_status = validated_data.get('status', instance.status)
        new_aadhar_no = validated_data.get('aadhar_no', instance.aadhar_no)
        validated_data['aadhar_no_hash'] = Student.hash_aadhar(new_aadhar_no)
        previous_username = instance.user_id.username if instance.user_id else None

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if instance.user_id:
            instance.user_id.username = new_register_number
            instance.user_id.is_active = str(new_status).lower() == 'active'
            if previous_username != new_register_number:
                instance.user_id.password_hash = make_password(new_register_number)
            instance.user_id.save()

        instance.save()
        return instance
