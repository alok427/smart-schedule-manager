"""
Shared enums/constants used across the Smart Schedule Manager apps.
Centralised here so the generator, validators, models and APIs all agree
on the same vocabulary instead of redefining it per-app.
"""

from django.db import models


class Role(models.TextChoices):
    SUPER_ADMIN = "SUPER_ADMIN", "Super Admin"
    DEPT_ADMIN = "DEPT_ADMIN", "Department Admin / HOD"
    FACULTY = "FACULTY", "Faculty"
    STUDENT = "STUDENT", "Student"


class SemesterType(models.TextChoices):
    ODD = "ODD", "Odd"
    EVEN = "EVEN", "Even"


class Day(models.IntegerChoices):
    MONDAY = 0, "Monday"
    TUESDAY = 1, "Tuesday"
    WEDNESDAY = 2, "Wednesday"
    THURSDAY = 3, "Thursday"
    FRIDAY = 4, "Friday"
    SATURDAY = 5, "Saturday"


class SessionType(models.TextChoices):
    LECTURE = "LECTURE", "Lecture"
    TUTORIAL = "TUTORIAL", "Tutorial"
    PRACTICAL = "PRACTICAL", "Practical / Lab"


class RoomType(models.TextChoices):
    CLASSROOM = "CLASSROOM", "Normal Classroom"
    LAB = "LAB", "Lab"
    OTHER = "OTHER", "Other"


class FacultyType(models.TextChoices):
    REGULAR = "REGULAR", "Regular / Primary Faculty"
    SUPPORTING = "SUPPORTING", "Supporting Faculty"
    ADDITIONAL = "ADDITIONAL", "Additional Faculty"
    RESTRICTED = "RESTRICTED", "Restricted / Manual-only Faculty"


class SubjectCategory(models.TextChoices):
    CORE = "CORE", "Core / Main"
    EXTRA = "EXTRA", "Additional / Extra"


class GenerationScopeType(models.TextChoices):
    COMPLETE = "COMPLETE", "Generate Complete Timetable"
    SECTION = "SECTION", "Selected Section"
    DRAFT = "DRAFT", "Draft / Temporary"


class GenerationStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    RUNNING = "RUNNING", "Running"
    DRAFT = "DRAFT", "Draft"
    TEMPORARY = "TEMPORARY", "Temporary"
    CURRENT = "CURRENT", "Current"
    HISTORICAL = "HISTORICAL", "Historical"
    FAILED = "FAILED", "Failed"


class ChangeSource(models.TextChoices):
    GENERATOR = "GENERATOR", "Generator"
    MANUAL_EDIT = "MANUAL_EDIT", "Manual Edit"
    FACULTY_SWAP = "FACULTY_SWAP", "Faculty Swap"
    ROOM_CHANGE = "ROOM_CHANGE", "Room Change"
    RESTORE = "RESTORE", "Restore"
    IMPORT = "IMPORT", "Excel Import"


# --- Official time slots (Section 11 / 13 of the spec) --------------------
# (start, end, is_break, label)
TIME_SLOTS = [
    ("09:45", "10:35", False, "P1"),
    ("10:35", "11:25", False, "P2"),
    ("11:25", "11:30", True, "SHORT BREAK"),
    ("11:30", "12:20", False, "P3"),
    ("12:20", "13:10", False, "P4"),
    ("13:10", "13:40", True, "LUNCH"),
    ("13:40", "14:30", False, "P5"),
    ("14:30", "15:20", False, "P6"),
    ("15:20", "16:05", False, "P7"),
    ("16:05", "16:50", False, "P8"),
]

# Valid two-period lab pairs, referenced by period label (Section 13).
LAB_PAIRS = [
    ("P1", "P2"),
    ("P3", "P4"),
    ("P5", "P6"),
    ("P7", "P8"),
]

LECTURE_DURATION_MINUTES = 50
