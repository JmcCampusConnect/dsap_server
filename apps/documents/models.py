from django.db import models


class Document(models.Model):
    
    id = models.BigAutoField(primary_key=True)

    request_id = models.ForeignKey(
        'requests.Request',
        on_delete=models.CASCADE,
        db_column='request_id'
    )

    service_document_id = models.ForeignKey(
        'services.ServiceDocument',
        on_delete=models.RESTRICT,
        db_column='service_document_id'
    )

    file_path = models.CharField(max_length=500)

    file_hash = models.CharField(max_length=64)

    verification_status = models.CharField(
        max_length=20,
        default='PENDING'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'document'

    def __str__(self):
        return self.file_path