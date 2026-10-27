from rest_framework import serializers

from .models import ImportBatch


class ImportBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportBatch
        fields = [
            "id", "original_filename", "status", "department",
            "faculty_imported", "subjects_imported", "classrooms_imported",
            "warning_count", "error_count", "warnings", "errors",
            "uploaded_by", "created_at",
        ]
        read_only_fields = fields
