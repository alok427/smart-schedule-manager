from django.core.exceptions import ValidationError
from django.db import models

from common.constants import SemesterType, SubjectCategory
from common.models import TimeStampedModel


class College(TimeStampedModel):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=20, unique=True)
    address = models.TextField(blank=True)
    logo = models.ImageField(upload_to="college_logos/", null=True, blank=True)

    def __str__(self):
        return self.name


class AcademicYear(TimeStampedModel):
    """e.g. '2025-2026'. Exactly one should be `is_active` at a time; the
    generator always operates against the active academic year unless a
    scope explicitly overrides it."""

    label = models.CharField(max_length=20, unique=True, help_text="e.g. 2025-2026")
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=False)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return self.label

    def clean(self):
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValidationError("Academic year start_date must be before end_date.")


class Department(TimeStampedModel):
    college = models.ForeignKey(College, on_delete=models.PROTECT, related_name="departments")
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=20, help_text="e.g. CSE, ECE, MECH")
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["college", "code"], name="uniq_department_code_per_college"),
        ]
        ordering = ["name"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class Year(TimeStampedModel):
    """A program year (1st..4th) within a department. `is_active` is the
    Section 7 'Year ON/OFF' control: turning it off excludes the year from
    generation without ever deleting its data."""

    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="years")
    year_number = models.PositiveSmallIntegerField(choices=[(i, f"Year {i}") for i in range(1, 5)])
    is_active = models.BooleanField(
        default=True,
        help_text="OFF excludes this year from generation. Never deletes underlying data.",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["department", "year_number"], name="uniq_year_per_department"),
        ]
        ordering = ["department_id", "year_number"]

    def __str__(self):
        return f"{self.department.code} Year {self.year_number}"

    @property
    def odd_semester_number(self):
        return (self.year_number * 2) - 1

    @property
    def even_semester_number(self):
        return self.year_number * 2


class Semester(TimeStampedModel):
    """A concrete semester instance (e.g. CSE Year 2, Semester 4, Even,
    2025-2026). The generation scope always targets one Semester type
    (Odd/Even) at a time across the selected departments/years."""

    year = models.ForeignKey(Year, on_delete=models.CASCADE, related_name="semesters")
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name="semesters")
    semester_number = models.PositiveSmallIntegerField()
    semester_type = models.CharField(max_length=4, choices=SemesterType.choices)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["year", "academic_year", "semester_number"],
                name="uniq_semester_per_year_academic_year",
            ),
        ]
        ordering = ["academic_year_id", "year_id", "semester_number"]

    def __str__(self):
        return f"{self.year} - Sem {self.semester_number} ({self.get_semester_type_display()})"

    def clean(self):
        expected_type = SemesterType.ODD if self.semester_number % 2 == 1 else SemesterType.EVEN
        if self.semester_type != expected_type:
            raise ValidationError(
                f"Semester {self.semester_number} must be marked {expected_type}, not {self.semester_type}."
            )


class Section(TimeStampedModel):
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="sections")
    year = models.ForeignKey(Year, on_delete=models.CASCADE, related_name="sections")
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name="sections")
    name = models.CharField(max_length=10, help_text="e.g. A, B, C")
    strength = models.PositiveIntegerField(default=0, help_text="Number of students")
    fixed_classroom = models.ForeignKey(
        "classrooms.Classroom",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="fixed_sections",
        help_text="Section 31: if set, the generator prefers/uses this room consistently for this section.",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["department", "year", "academic_year", "name"],
                name="uniq_section_per_year_academic_year",
            ),
        ]
        ordering = ["department_id", "year_id", "name"]

    def __str__(self):
        return f"{self.department.code} Y{self.year.year_number} - {self.name}"


class Batch(TimeStampedModel):
    """Lab sub-batch of a Section (e.g. Section A -> Batch A1/A2). See
    Section 14 (lab batches) of the spec."""

    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="batches")
    name = models.CharField(max_length=10, help_text="e.g. B1, B2")
    strength = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["section", "name"], name="uniq_batch_per_section"),
        ]
        ordering = ["section_id", "name"]

    def __str__(self):
        return f"{self.section} / {self.name}"


class Subject(TimeStampedModel):
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="subjects")
    year = models.ForeignKey(Year, on_delete=models.CASCADE, related_name="subjects")
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=10, choices=SubjectCategory.choices, default=SubjectCategory.CORE)

    lecture_hours = models.PositiveSmallIntegerField(default=0, help_text="Weekly lecture hours")
    tutorial_hours = models.PositiveSmallIntegerField(default=0, help_text="Weekly tutorial hours")
    practical_hours = models.PositiveSmallIntegerField(
        default=0, help_text="Weekly practical hours (converted to 2-period lab blocks)"
    )
    credits = models.DecimalField(max_digits=4, decimal_places=1, default=0)

    has_batches = models.BooleanField(default=False)
    num_batches = models.PositiveSmallIntegerField(default=1)
    allow_multiple_faculty = models.BooleanField(
        default=False,
        help_text="Section 18: normally one faculty per subject unless explicitly allowed.",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["department", "code"], name="uniq_subject_code_per_department"),
        ]
        ordering = ["department_id", "year_id", "code"]

    def __str__(self):
        return f"{self.code} - {self.name}"

    @property
    def requires_lab(self):
        return self.practical_hours > 0

    @property
    def required_lab_blocks(self):
        """Practical hours are scheduled as 2-period blocks (Section 15)."""
        import math

        return math.ceil(self.practical_hours / 2)

    def clean(self):
        if self.practical_hours % 2 != 0:
            raise ValidationError(
                "practical_hours should be an even number: practicals are scheduled as 2-period lab blocks."
            )


class SubjectOffering(TimeStampedModel):
    """A Subject as actually offered to a specific Section in a specific
    Semester. This is the unit the generator schedules sessions for, and
    the level at which faculty is assigned/overridden (Section 33)."""

    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="offerings")
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="subject_offerings")
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name="subject_offerings")
    faculty = models.ForeignKey(
        "faculty.Faculty",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="subject_offerings",
    )
    is_faculty_locked = models.BooleanField(
        default=False,
        help_text="If true, regeneration/override must not silently change the assigned faculty.",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["subject", "section", "semester"], name="uniq_offering_per_subject_section_semester"
            ),
        ]
        ordering = ["section_id", "subject_id"]

    def __str__(self):
        return f"{self.subject.code} -> {self.section} ({self.semester})"
