from django.core.exceptions import ValidationError
from django.db import models

from common.constants import Day, FacultyType, SubjectCategory
from common.models import TimeStampedModel


class Faculty(TimeStampedModel):
    """
    Core faculty entity. IMPORTANT (Section 19/20): a Faculty row existing
    in the database does NOT make them auto-eligible for every subject.
    Eligibility for SUPPORTING/ADDITIONAL/RESTRICTED types is governed by
    FacultyAssignmentRule; only REGULAR faculty are broadly auto-assignable
    (still subject to FacultySubjectPreference/eligibility checks).
    """

    user = models.OneToOneField(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="faculty_profile"
    )
    department = models.ForeignKey("academics.Department", on_delete=models.CASCADE, related_name="faculty_members")
    name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    short_code = models.CharField(max_length=15, unique=True, help_text="e.g. XYZ, used on timetable cells")
    designation = models.CharField(max_length=100, blank=True)

    faculty_type = models.CharField(max_length=12, choices=FacultyType.choices, default=FacultyType.REGULAR)

    max_lectures_per_day = models.PositiveSmallIntegerField(default=6)
    max_lectures_per_week = models.PositiveSmallIntegerField(default=24)
    min_additional_load_hours = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    max_additional_load_hours = models.DecimalField(max_digits=4, decimal_places=1, default=0)

    is_class_coordinator = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [models.Index(fields=["faculty_type"]), models.Index(fields=["department"])]
        ordering = ["department_id", "name"]
        verbose_name_plural = "Faculty"

    def __str__(self):
        return f"{self.short_code} - {self.name}"

    def clean(self):
        if self.max_lectures_per_day * 6 < self.max_lectures_per_week:
            # soft sanity check only — not a hard DB constraint
            pass


class FacultyProfile(TimeStampedModel):
    """Extended, optional profile info kept separate from the core Faculty
    record so the scheduling-critical fields on Faculty stay lean."""

    faculty = models.OneToOneField(Faculty, on_delete=models.CASCADE, related_name="profile")
    photo = models.ImageField(upload_to="faculty_photos/", null=True, blank=True)
    office_location = models.CharField(max_length=150, blank=True)
    bio = models.TextField(blank=True)
    qualification = models.CharField(max_length=255, blank=True)
    joining_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"Profile: {self.faculty}"


class FacultyAvailability(TimeStampedModel):
    """Recurring weekly time the faculty is NOT available to teach (Section
    17/28: hard constraint the generator must never violate)."""

    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE, related_name="unavailability_windows")
    day = models.IntegerField(choices=Day.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["faculty_id", "day", "start_time"]
        constraints = [
            models.UniqueConstraint(
                fields=["faculty", "day", "start_time", "end_time"], name="uniq_faculty_unavailability_window"
            )
        ]

    def __str__(self):
        return f"{self.faculty} unavailable {self.get_day_display()} {self.start_time}-{self.end_time}"


class FacultyPreference(TimeStampedModel):
    """General (non subject-specific) scheduling preferences — e.g. prefers
    mornings, prefers not to teach back-to-back on a given day. Soft
    constraints only; must never override hard constraints."""

    faculty = models.OneToOneField(Faculty, on_delete=models.CASCADE, related_name="preference")
    prefers_morning = models.BooleanField(default=False)
    prefers_no_back_to_back = models.BooleanField(default=False)
    preferred_days_off = models.JSONField(default=list, blank=True, help_text="List of Day ints, e.g. [5] for Saturday")
    max_consecutive_lectures = models.PositiveSmallIntegerField(default=3)

    def __str__(self):
        return f"Preferences for {self.faculty}"


class FacultySubjectPreference(TimeStampedModel):
    """Priority ranking of subjects a faculty is willing/able to teach.
    Used as ranking criterion #5 in Section 17, NOT as the sole eligibility
    rule — a faculty may still be assigned a subject outside this list if
    admin explicitly allows it (subject-level override, Section 33)."""

    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE, related_name="subject_preferences")
    subject = models.ForeignKey("academics.Subject", on_delete=models.CASCADE, related_name="faculty_preferences")
    priority = models.PositiveSmallIntegerField(default=5, help_text="Lower number = higher priority")
    is_eligible = models.BooleanField(
        default=True, help_text="Explicit eligibility flag, independent of priority ranking."
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["faculty", "subject"], name="uniq_faculty_subject_preference"),
        ]
        ordering = ["subject_id", "priority"]

    def __str__(self):
        return f"{self.faculty} -> {self.subject} (priority {self.priority})"


class FacultyAssignmentRule(TimeStampedModel):
    """
    Section 20/21: the configuration that governs SUPPORTING / ADDITIONAL /
    RESTRICTED faculty eligibility. If no rule exists for a
    supporting/additional/restricted faculty + subject/category, the
    generator MUST NOT assign them — this is enforced in the eligibility
    service (scheduling/services/eligibility.py), not just in the UI.
    """

    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE, related_name="assignment_rules")

    # Scope of what this rule grants access to. A rule may target specific
    # subjects, an entire category (CORE/EXTRA), or a department/domain.
    department = models.ForeignKey(
        "academics.Department", null=True, blank=True, on_delete=models.CASCADE, related_name="+"
    )
    subject = models.ForeignKey(
        "academics.Subject", null=True, blank=True, on_delete=models.CASCADE, related_name="assignment_rules"
    )
    subject_category = models.CharField(
        max_length=10, choices=SubjectCategory.choices, null=True, blank=True
    )

    allowed_years = models.JSONField(default=list, blank=True, help_text="List of Year.year_number ints, [] = all")
    allowed_semesters = models.JSONField(default=list, blank=True, help_text="List of semester numbers, [] = all")
    allowed_sections = models.ManyToManyField("academics.Section", blank=True, related_name="+")

    max_lectures = models.PositiveSmallIntegerField(null=True, blank=True)
    specific_lecture_count = models.PositiveSmallIntegerField(null=True, blank=True)

    preferred_day = models.IntegerField(choices=Day.choices, null=True, blank=True)
    preferred_slot_label = models.CharField(max_length=10, blank=True, help_text="e.g. P1, matches TIME_SLOTS label")
    fixed_day = models.IntegerField(choices=Day.choices, null=True, blank=True)
    fixed_slot_label = models.CharField(max_length=10, blank=True)

    is_generator_eligible = models.BooleanField(
        default=True,
        help_text="If False, this faculty can ONLY be assigned manually — the generator must skip them.",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["faculty_id"]

    def __str__(self):
        target = self.subject or self.subject_category or self.department or "any"
        return f"Rule: {self.faculty} -> {target}"

    def clean(self):
        if not any([self.department_id, self.subject_id, self.subject_category]):
            raise ValidationError(
                "An assignment rule must scope to at least a department, subject, or subject category."
            )


class FacultyLoad(TimeStampedModel):
    """
    Materialised workload snapshot for a faculty within a given generation
    + semester (Section 22). Recomputed after generation, modification,
    swap, restore, and publishing — never hand-edited directly.
    """

    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE, related_name="loads")
    generation = models.ForeignKey(
        "scheduling.TimetableGeneration", on_delete=models.CASCADE, related_name="faculty_loads"
    )
    semester = models.ForeignKey("academics.Semester", on_delete=models.CASCADE, related_name="faculty_loads")

    lecture_count = models.PositiveSmallIntegerField(default=0)
    tutorial_count = models.PositiveSmallIntegerField(default=0)
    practical_periods = models.PositiveSmallIntegerField(default=0)
    additional_load_hours = models.DecimalField(max_digits=5, decimal_places=1, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["faculty", "generation", "semester"], name="uniq_faculty_load_per_generation"
            ),
        ]
        ordering = ["generation_id", "faculty_id"]

    def __str__(self):
        return f"Load: {self.faculty} @ {self.generation}"

    @property
    def total_teaching_periods(self):
        return self.lecture_count + self.tutorial_count + self.practical_periods
