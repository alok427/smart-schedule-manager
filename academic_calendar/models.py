from django.db import models

from common.constants import Day
from common.models import TimeStampedModel


class AcademicCalendar(TimeStampedModel):
    """One calendar per (academic_year, department-or-college-wide). The
    generator must consult this before scheduling any normal class
    (Section 26): no normal classes on non-working days."""

    academic_year = models.ForeignKey(
        "academics.AcademicYear", on_delete=models.CASCADE, related_name="calendars"
    )
    department = models.ForeignKey(
        "academics.Department",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="calendars",
        help_text="Null = applies college-wide.",
    )
    semester_start = models.DateField()
    semester_end = models.DateField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["academic_year", "department"], name="uniq_calendar_per_year_department"
            ),
        ]
        ordering = ["academic_year_id"]

    def __str__(self):
        scope = self.department.code if self.department else "College-wide"
        return f"Calendar {self.academic_year} ({scope})"


class WorkingDay(TimeStampedModel):
    """Default weekly working-day pattern for a calendar (e.g. Mon-Fri
    working, Saturday alternate/off). Overridden per-date by Holiday /
    SpecialWorkingDay."""

    calendar = models.ForeignKey(AcademicCalendar, on_delete=models.CASCADE, related_name="working_days")
    day = models.IntegerField(choices=Day.choices)
    is_working = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["calendar", "day"], name="uniq_working_day_per_calendar"),
        ]
        ordering = ["calendar_id", "day"]

    def __str__(self):
        return f"{self.calendar}: {self.get_day_display()} {'Working' if self.is_working else 'Off'}"


class Holiday(TimeStampedModel):
    calendar = models.ForeignKey(AcademicCalendar, on_delete=models.CASCADE, related_name="holidays")
    date = models.DateField()
    name = models.CharField(max_length=200)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["calendar", "date"], name="uniq_holiday_per_calendar_date"),
        ]
        indexes = [models.Index(fields=["date"])]
        ordering = ["date"]

    def __str__(self):
        return f"{self.name} ({self.date})"


class SpecialWorkingDay(TimeStampedModel):
    """A date that would normally be off (e.g. a Saturday, or a declared
    holiday) but is explicitly made a working day, following another
    weekday's timetable pattern (e.g. "this Saturday follows Monday's
    schedule")."""

    calendar = models.ForeignKey(AcademicCalendar, on_delete=models.CASCADE, related_name="special_working_days")
    date = models.DateField()
    name = models.CharField(max_length=200, blank=True)
    follows_day_schedule = models.IntegerField(
        choices=Day.choices, help_text="Which weekday's timetable pattern to use on this date."
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["calendar", "date"], name="uniq_special_working_day_per_calendar_date"),
        ]
        ordering = ["date"]

    def __str__(self):
        return f"{self.date} follows {self.get_follows_day_schedule_display()}"


class Event(TimeStampedModel):
    """Institutional event. `affects_timetable=True` means the generator
    must block the given slots (or whole day) from normal scheduling —
    but only when explicitly configured, per Section 24."""

    calendar = models.ForeignKey(AcademicCalendar, on_delete=models.CASCADE, related_name="events")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    affects_timetable = models.BooleanField(default=False)

    class Meta:
        indexes = [models.Index(fields=["start_date", "end_date"])]
        ordering = ["start_date"]

    def __str__(self):
        return f"{self.name} ({self.start_date} - {self.end_date})"
