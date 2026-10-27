from django.db import models

from common.models import TimeStampedModel


class NotificationCategory(models.TextChoices):
    TIMETABLE_GENERATED = "TIMETABLE_GENERATED", "Timetable Generated"
    TIMETABLE_PUBLISHED = "TIMETABLE_PUBLISHED", "Timetable Published"
    TIMETABLE_UPDATED = "TIMETABLE_UPDATED", "Timetable Updated"
    FACULTY_CHANGED = "FACULTY_CHANGED", "Faculty Changed"
    CLASSROOM_CHANGED = "CLASSROOM_CHANGED", "Classroom Changed"
    TIMETABLE_RESTORED = "TIMETABLE_RESTORED", "Timetable Restored"
    CONFLICT_WARNING = "CONFLICT_WARNING", "Conflict / Warning"
    GENERATION_FAILED = "GENERATION_FAILED", "Generation Failed"
    IMPORT_SUMMARY = "IMPORT_SUMMARY", "Excel Import Summary"


class Notification(TimeStampedModel):
    """
    The single, coherent in-app notification model (Section 58 — no
    duplicate notification models/delivery logic anywhere else in the
    project). Delivery (in-app + optional email) is handled by
    notifications/services.py, which everything else calls into.
    """

    recipient = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="notifications"
    )
    category = models.CharField(max_length=25, choices=NotificationCategory.choices)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    link = models.CharField(max_length=500, blank=True, help_text="Optional frontend deep-link, e.g. /timetable/42")
    data = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["recipient", "is_read"])]

    def __str__(self):
        return f"[{self.category}] {self.title} -> {self.recipient}"
