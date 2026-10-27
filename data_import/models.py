from django.db import models

from common.models import TimeStampedModel


class ImportBatch(TimeStampedModel):
    """
    Record of one Excel import attempt (Section 54). Kept even for failed
    imports so admins can see import history and re-download the offending
    file's error report. Imports are transactional (Section 54): if
    critical/required data is invalid, nothing from that sheet is
    committed — see data_import/services.py.
    """

    STATUS_CHOICES = [
        ("SUCCESS", "Success"),
        ("PARTIAL", "Partial (warnings only)"),
        ("FAILED", "Failed (rejected)"),
    ]

    uploaded_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="import_batches"
    )
    department = models.ForeignKey(
        "academics.Department", null=True, blank=True, on_delete=models.SET_NULL, related_name="import_batches"
    )
    original_filename = models.CharField(max_length=255)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)

    faculty_imported = models.PositiveIntegerField(default=0)
    subjects_imported = models.PositiveIntegerField(default=0)
    classrooms_imported = models.PositiveIntegerField(default=0)
    warning_count = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)

    warnings = models.JSONField(default=list, blank=True)
    errors = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Import {self.original_filename} [{self.status}] @ {self.created_at:%Y-%m-%d %H:%M}"
