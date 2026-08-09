import csv
import io

from django.db import transaction
from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from apps.accounts.models import Role
from apps.audit.models import AuditLog
from common.pagination import StandardPagination

from .models import Student
from .permissions import IsStudentManagementAdmin
from .serializers import StudentSerializer


class StudentViewSet(viewsets.ModelViewSet):
    serializer_class = StudentSerializer
    pagination_class = StandardPagination
    permission_classes = [IsStudentManagementAdmin]

    def get_queryset(self):
        queryset = (
            Student.objects.select_related('user_id', 'academic_department_id')
            .all()
            .order_by('register_number')
        )

        include_inactive = self.request.query_params.get('include_inactive', '').lower() in {
            'true',
            '1',
            'yes',
        }
        status_filter = self.request.query_params.get('status', '').strip()

        if status_filter:
            queryset = queryset.filter(status__iexact=status_filter)
        elif not include_inactive:
            queryset = queryset.exclude(status__iexact='inactive')

        search = self.request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(register_number__icontains=search)
                | Q(mobile_number__icontains=search)
                | Q(date_of_birth__icontains=search)
                | Q(religion__icontains=search)
                | Q(address_line1__icontains=search)
                | Q(address_line2__icontains=search)
                | Q(city__icontains=search)
                | Q(district__icontains=search)
                | Q(state__icontains=search)
                | Q(pincode__icontains=search)
                | Q(father_name__icontains=search)
                | Q(mother_name__icontains=search)
                | Q(guardian_name__icontains=search)
                | Q(parent_mobile_number__icontains=search)
                | Q(academic_department_id__code__icontains=search)
                | Q(academic_department_id__degree__icontains=search)
                | Q(academic_department_id__branch__icontains=search)
            )

        filters = {
            'register_number__iexact': self.request.query_params.get('register_number', '').strip(),
            'batch_year__iexact': self.request.query_params.get('batch_year', '').strip(),
            'section__iexact': self.request.query_params.get('section', '').strip(),
            'stream__iexact': self.request.query_params.get('stream', '').strip(),
        }

        for lookup, value in filters.items():
            if value:
                queryset = queryset.filter(**{lookup: value})

        department_id = self.request.query_params.get('academic_department_id', '').strip()
        if department_id:
            queryset = queryset.filter(academic_department_id_id=department_id)

        return queryset

    def perform_create(self, serializer):
        with transaction.atomic():
            instance = serializer.save()
            AuditLog.log(
                request=self.request,
                action='CREATE',
                obj=instance,
                changes=self.get_serializer(instance).data,
            )

    def perform_update(self, serializer):
        with transaction.atomic():
            instance = self.get_object()
            old_data = self.get_serializer(instance).data
            updated_instance = serializer.save()
            new_data = self.get_serializer(updated_instance).data

            changes = {}
            for key, new_value in new_data.items():
                if old_data.get(key) != new_value:
                    changes[key] = {
                        'old': old_data.get(key),
                        'new': new_value,
                    }

            if changes:
                AuditLog.log(
                    request=self.request,
                    action='UPDATE',
                    obj=updated_instance,
                    changes=changes,
                )

    def destroy(self, request, *args, **kwargs):
        with transaction.atomic():
            instance = self.get_object()
            snapshot = self.get_serializer(instance).data

            instance.status = Student.StatusChoices.INACTIVE
            instance.save(update_fields=['status', 'updated_at'])

            if instance.user_id:
                instance.user_id.is_active = False
                instance.user_id.save(update_fields=['is_active', 'updated_at'])

            AuditLog.log(
                request=request,
                action='DELETE',
                obj=instance,
                object_id=instance.pk,
                changes=snapshot,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=False,
        methods=['post'],
        url_path='bulk-import',
        parser_classes=[MultiPartParser, FormParser],
    )
    def bulk_import(self, request):
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response(
                {'error': 'No file uploaded.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            file_content = uploaded_file.read().decode('utf-8-sig')
        except UnicodeDecodeError:
            return Response(
                {'error': 'Invalid CSV file encoding.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reader = csv.DictReader(io.StringIO(file_content))
        expected_headers = [
            'register_number',
            'academic_department_id',
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
        ]

        headers = [str(header).strip().lower() for header in (reader.fieldnames or [])]
        if headers != expected_headers:
            return Response(
                {
                    'error': 'Invalid headers.',
                    'expected': expected_headers,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not Role.objects.filter(name='STUDENT').exists():
            return Response(
                {'error': 'STUDENT role does not exist.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        seen_register_numbers = set()
        seen_aadhars = set()
        serializers_to_save = []
        row_errors = []

        for row_index, row in enumerate(reader, start=2):
            row_data = {}
            for header in expected_headers:
                value = row.get(header, '')
                row_data[header] = value.strip() if isinstance(value, str) else value

            register_number = (row_data.get('register_number') or '').strip()
            aadhar_no = (row_data.get('aadhar_no') or '').strip()

            current_errors = []

            if register_number:
                register_key = register_number.lower()
                if register_key in seen_register_numbers:
                    current_errors.append('Duplicate register number found in uploaded file.')
                else:
                    seen_register_numbers.add(register_key)

            if aadhar_no:
                if aadhar_no in seen_aadhars:
                    current_errors.append('Duplicate Aadhar number found in uploaded file.')
                else:
                    seen_aadhars.add(aadhar_no)

            serializer = self.get_serializer(data=row_data)
            if not serializer.is_valid():
                current_errors.append(serializer.errors)

            if current_errors:
                row_errors.append(
                    {
                        'row': row_index,
                        'errors': current_errors,
                    }
                )
            else:
                serializers_to_save.append(serializer)

        if row_errors:
            return Response(
                {
                    'error': 'Validation failed for some rows.',
                    'details': row_errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        created_count = 0
        with transaction.atomic():
            for serializer in serializers_to_save:
                serializer.save()
                created_count += 1

            AuditLog.log(
                request=request,
                action='IMPORT',
                obj=Student,
                object_id='BULK_IMPORT',
                object_repr='Imported Students',
                changes={'imported_count': created_count},
            )

        return Response(
            {'message': f'Successfully imported {created_count} students.'},
            status=status.HTTP_201_CREATED,
        )
