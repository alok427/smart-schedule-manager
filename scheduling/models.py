from django.db import models

from common.constants import (
    ChangeSource,
    Day,
    GenerationScopeType,
    GenerationStatus,
    SessionType,
)
from common.models import AuditModel, TimeStampedModel


class TimetableGeneration(AuditModel):
    """
    One generation *run* (Section 40). A single run may cover many
    departments/years/sections ("Generate Complete") or just one
    ("Generate Selected Section") or be a non-activating Draft.

    Activation is handled at the TimetableVersion level (per section), so a
    complete-generation run can partially fail without ever touching
    sections that succeeded — see Section 10 (atomic generation) and
    Section 44 (Current/Draft/Historical).
    """

    academic_year = models.ForeignKey("academics.AcademicYear", on_delete=models.CASCADE, related_name="generations")
    semester_type = models.CharField(max_length=4)  # ODD / EVEN, mirrors common.constants.SemesterType

    scope_type = models.CharField(max_length=10, choices=GenerationScopeType.choices)
    departments = models.ManyToManyField("academics.Department", blank=True, related_name="+")
    years = models.ManyToManyField("academics.Year", blank=True, related_name="+")
    sections = models.ManyToManyField(
        "academics.Section", blank=True, related_name="generations", help_text="Resolved concrete scope."
    )

    status = models.CharField(max_length=12, choices=GenerationStatus.choices, default=GenerationStatus.PENDING)
    seed = models.BigIntegerField(
        null=True, blank=True, help_text="Deterministic RNG seed used for any tie-breaking during generation."
    )

    parent_generation = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="regenerations",
        help_text="If this run was a regeneration, points at the run it superseded.",
    )

    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    failure_summary = models.TextField(
        blank=True, help_text="Top-line reason if status=FAILED. Detail lives in GenerationIssue rows."
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status"]), models.Index(fields=["academic_year", "semester_type"])]

    def __str__(self):
        return f"Generation #{self.pk} [{self.status}] ({self.academic_year}, {self.semester_type})"


class GenerationIssue(TimeStampedModel):
    """Structured 'WHAT failed and WHY' record (Sections 10, 38, 73) —
    never just a bare exception name."""

    SEVERITY_CHOICES = [("ERROR", "Error"), ("WARNING", "Warning"), ("INFO", "Info")]

    generation = models.ForeignKey(TimetableGeneration, on_delete=models.CASCADE, related_name="issues")
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default="ERROR")
    section = models.ForeignKey(
        "academics.Section", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    subject = models.ForeignKey(
        "academics.Subject", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    message = models.TextField(help_text="Human-readable explanation, e.g. 'DBMS Lab for CSE Section 1 could not "
                                          "be scheduled because no suitable lab is available in any valid "
                                          "two-period slot.'")

    class Meta:
        ordering = ["generation_id", "-severity"]

    def __str__(self):
        return f"[{self.severity}] {self.message[:80]}"


class TimetableSession(TimeStampedModel):
    """
    A discrete schedulable unit derived from a SubjectOffering's required
    hours (Section 15): e.g. 'Lecture #2 of 3' or 'Practical block #1 of
    1'. Built once per generation before placement begins (generator step
    14 in Section 37).
    """

    generation = models.ForeignKey(TimetableGeneration, on_delete=models.CASCADE, related_name="sessions")
    subject_offering = models.ForeignKey(
        "academics.SubjectOffering", on_delete=models.CASCADE, related_name="timetable_sessions"
    )
    batch = models.ForeignKey(
        "academics.Batch", null=True, blank=True, on_delete=models.CASCADE, related_name="timetable_sessions"
    )
    session_type = models.CharField(max_length=10, choices=SessionType.choices)
    sequence_number = models.PositiveSmallIntegerField(default=1)
    duration_periods = models.PositiveSmallIntegerField(
        default=1, help_text="1 for lecture/tutorial periods, 2 for a practical lab block."
    )
    is_scheduled = models.BooleanField(default=False)

    class Meta:
        ordering = ["subject_offering_id", "session_type", "sequence_number"]
        indexes = [models.Index(fields=["generation", "is_scheduled"])]

    def __str__(self):
        return f"{self.subject_offering} - {self.get_session_type_display()} #{self.sequence_number}"


class FixedLecture(AuditModel):
    """
    Admin-defined lock (Section 27). Loaded and reserved FIRST, before
    anything else is scheduled (Section 37, steps 8-13). Conflicting fixed
    lectures are never auto-modified (Section 28) — they're surfaced to the
    admin as GenerationIssue rows instead.
    """

    academic_year = models.ForeignKey("academics.AcademicYear", on_delete=models.CASCADE, related_name="+")
    subject_offering = models.ForeignKey(
        "academics.SubjectOffering", on_delete=models.CASCADE, related_name="fixed_lectures"
    )
    batch = models.ForeignKey(
        "academics.Batch", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    session_type = models.CharField(max_length=10, choices=SessionType.choices)

    faculty = models.ForeignKey(
        "faculty.Faculty", null=True, blank=True, on_delete=models.SET_NULL, related_name="fixed_lectures"
    )
    classroom = models.ForeignKey(
        "classrooms.Classroom", null=True, blank=True, on_delete=models.SET_NULL, related_name="fixed_lectures"
    )
    day = models.IntegerField(choices=Day.choices)
    period_label = models.CharField(max_length=10, help_text="e.g. P1; for labs this is the first of the pair.")

    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["day", "period_label"]

    def __str__(self):
        return f"FIXED: {self.subject_offering} {self.get_day_display()} {self.period_label}"


class TimetableEntry(TimeStampedModel):
    """
    One 50-minute period, placed. A 2-period lab block is stored as two
    TimetableEntry rows sharing the same `session` (and therefore the same
    faculty/room/section/day by construction) — grouped back together for
    display (Section 13/76) rather than merged in storage, so every
    conflict check operates on a uniform "one resource, one period" unit.

    Uniqueness constraints below enforce the hard constraints (Section 35)
    *within a single generation*. Cross-generation "global" conflicts
    (Section 9) against the currently CURRENT timetable are enforced by the
    central validation service (scheduling/services/validation.py), since
    two independent DRAFTs are allowed to coexist unvalidated against each
    other until one of them is published.
    """

    generation = models.ForeignKey(TimetableGeneration, on_delete=models.CASCADE, related_name="entries")
    session = models.ForeignKey(TimetableSession, on_delete=models.CASCADE, related_name="entries")

    section = models.ForeignKey("academics.Section", on_delete=models.CASCADE, related_name="timetable_entries")
    batch = models.ForeignKey(
        "academics.Batch", null=True, blank=True, on_delete=models.SET_NULL, related_name="timetable_entries"
    )
    faculty = models.ForeignKey(
        "faculty.Faculty", null=True, blank=True, on_delete=models.SET_NULL, related_name="timetable_entries"
    )
    classroom = models.ForeignKey(
        "classrooms.Classroom", null=True, blank=True, on_delete=models.SET_NULL, related_name="timetable_entries"
    )

    day = models.IntegerField(choices=Day.choices)
    period_label = models.CharField(max_length=10)
    start_time = models.TimeField()
    end_time = models.TimeField()

    is_fixed = models.BooleanField(default=False)
    fixed_lecture = models.ForeignKey(
        FixedLecture, null=True, blank=True, on_delete=models.SET_NULL, related_name="generated_entries"
    )

    class Meta:
        ordering = ["day", "start_time"]
        indexes = [
            models.Index(fields=["generation", "day", "period_label"]),
            models.Index(fields=["generation", "faculty"]),
            models.Index(fields=["generation", "classroom"]),
            models.Index(fields=["generation", "section"]),
        ]
        constraints = [
            # Section clash (a section can't be in two places at once) —
            # batch-aware: two different batches of the SAME section may
            # legitimately be in different labs at the same time.
            models.UniqueConstraint(
                fields=["generation", "section", "batch", "day", "period_label"],
                name="uniq_section_batch_slot_per_generation",
            ),
            models.UniqueConstraint(
                fields=["generation", "faculty", "day", "period_label"],
                name="uniq_faculty_slot_per_generation",
                condition=models.Q(faculty__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["generation", "classroom", "day", "period_label"],
                name="uniq_classroom_slot_per_generation",
                condition=models.Q(classroom__isnull=False),
            ),
        ]

    def __str__(self):
        return f"{self.section} {self.get_day_display()} {self.period_label}: {self.session}"


class TimetableVersion(AuditModel):
    """
    Section-scoped version pointer (Section 40/41/44/78). This is what
    "Current" actually means in practice: exactly one CURRENT
    TimetableVersion per (section, semester). Restoring a historical
    version flips this pointer — it must NEVER call the generator again
    (Section 41/78).
    """

    section = models.ForeignKey("academics.Section", on_delete=models.CASCADE, related_name="versions")
    semester = models.ForeignKey("academics.Semester", on_delete=models.CASCADE, related_name="versions")
    generation = models.ForeignKey(TimetableGeneration, on_delete=models.CASCADE, related_name="versions")

    version_number = models.PositiveIntegerField()
    status = models.CharField(max_length=12, choices=GenerationStatus.choices, default=GenerationStatus.DRAFT)
    activated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-version_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["section", "semester", "version_number"], name="uniq_version_number_per_section_semester"
            ),
            models.UniqueConstraint(
                fields=["section", "semester"],
                condition=models.Q(status="CURRENT"),
                name="uniq_current_version_per_section_semester",
            ),
        ]

    def __str__(self):
        return f"{self.section} v{self.version_number} [{self.status}]"


class TimetableChange(TimeStampedModel):
    """Audit trail (Section 79) for anything that alters a published
    timetable: manual edits, faculty swaps, room changes, restores,
    imports. Powers 'who changed what, when, why'."""

    version = models.ForeignKey(
        TimetableVersion, null=True, blank=True, on_delete=models.CASCADE, related_name="changes"
    )
    entry = models.ForeignKey(
        TimetableEntry, null=True, blank=True, on_delete=models.SET_NULL, related_name="change_log"
    )
    source = models.CharField(max_length=15, choices=ChangeSource.choices)
    description = models.TextField()
    old_data = models.JSONField(null=True, blank=True)
    new_data = models.JSONField(null=True, blank=True)
    changed_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="timetable_changes"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["source"])]

    def __str__(self):
        return f"[{self.source}] {self.description[:80]}"
