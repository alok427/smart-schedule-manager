from django.contrib import admin

from .models import ImportBatch


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = ("original_filename", "status", "uploaded_by", "department",
                     "faculty_imported", "subjects_imported", "classrooms_imported",
                     "warning_count", "error_count", "created_at")
    list_filter = ("status", "department")
    readonly_fields = ("created_at",)
