from django.db import models

class Document(models.Model):
    request_id = models.ForeignKey('requests.Request', on_delete=models.CASCADE, db_column='request_id')
    service_document_id = models.ForeignKey('services.ServiceDocument', on_delete=models.RESTRICT, db_column='service_document_id')
    file_path = models.CharField(max_length=500)
    file_hash = models.CharField(max_length=64)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    verification_status = models.CharField(max_length=20, default='PENDING')

    class Meta:
        db_table = 'document'
