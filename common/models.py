from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    """Abstract base adding created/updated timestamps."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class AuditModel(TimeStampedModel):
    """
    Abstract base for models that need "who created / who last modified"
    auditability (Section 79). Uses SET_NULL so deleting a user account
    never silently deletes historical timetable/audit data.
    """

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="%(app_label)s_%(class)s_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="%(app_label)s_%(class)s_updated",
    )

    class Meta:
        abstract = True
