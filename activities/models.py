from django.db import models

from common.constants import Day
from common.models import TimeStampedModel


class Activity(TimeStampedModel):
    """Catalog of activity types (Saturday events, extracurricular,
    institutional activities). See Section 24."""

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    department = models.ForeignKey(
        "academics.Department", null=True, blank=True, on_delete=models.CASCADE, related_name="activities"
    )
    counts_toward_workload = models.BooleanField(
        default=False, help_text="Section 25: never silently counted as a normal lecture unless this is True."
    )
    is_academic_timetable_activity = models.BooleanField(
        default=False, help_text="True if this occupies a real timetable slot."
    )
    is_extra_activity = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Activities"

    def __str__(self):
        return self.name


class FacultyActivity(TimeStampedModel):
    """A specific instance of an Activity assigned to a faculty member,
    optionally tied to a section/slot. Must never automatically consume a
    normal teaching slot unless explicitly configured (Section 24)."""

    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name="faculty_activities")
    faculty = models.ForeignKey("faculty.Faculty", on_delete=models.CASCADE, related_name="activities")
    section = models.ForeignKey(
        "academics.Section", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    date = models.DateField(null=True, blank=True)
    day = models.IntegerField(choices=Day.choices, null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    load_value_hours = models.DecimalField(max_digits=4, decimal_places=1, default=0)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.activity} - {self.faculty}"

    @property
    def counts_toward_workload(self):
        return self.activity.counts_toward_workload


class CoordinatorAssignment(TimeStampedModel):
    """Class coordinator assignment (Section 23), tracked separately from
    normal teaching load."""

    faculty = models.ForeignKey("faculty.Faculty", on_delete=models.CASCADE, related_name="coordinator_assignments")
    section = models.ForeignKey("academics.Section", on_delete=models.CASCADE, related_name="coordinator_assignments")
    academic_year = models.ForeignKey("academics.AcademicYear", on_delete=models.CASCADE, related_name="+")
    load_value_hours = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["section", "academic_year"],
                condition=models.Q(is_active=True),
                name="uniq_active_coordinator_per_section_year",
            ),
        ]
        ordering = ["section_id"]

    def __str__(self):
        return f"{self.faculty} coordinates {self.section} ({self.academic_year})"


class AdditionalLoad(TimeStampedModel):
    """General ledger of additional (non-teaching) load for a faculty in a
    semester — coordinator duty, institutional committees, etc. — kept
    explicitly separate from normal teaching load (Section 25)."""

    faculty = models.ForeignKey("faculty.Faculty", on_delete=models.CASCADE, related_name="additional_loads")
    semester = models.ForeignKey("academics.Semester", on_delete=models.CASCADE, related_name="additional_loads")
    description = models.CharField(max_length=255)
    load_value_hours = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    counts_toward_workload = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.faculty}: {self.description} ({self.load_value_hours}h)"
