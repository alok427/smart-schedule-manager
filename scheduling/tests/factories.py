"""
Builds a small, realistic academic scope for tests: one department, one
year/semester, one section with two lab batches, a handful of subjects
(including a batched practical), a couple of classrooms/labs, and two
faculty. Deliberately independent of the `seed_demo_data` management
command so tests don't depend on (or break when someone edits) the demo
fixture.
"""

from datetime import date

from academic_calendar.models import AcademicCalendar, WorkingDay
from academics.models import (
    AcademicYear,
    Batch,
    College,
    Department,
    Section,
    Semester,
    Subject,
    SubjectOffering,
    Year,
)
from classrooms.models import Classroom
from common.constants import Day, RoomType, SemesterType, SubjectCategory
from faculty.models import Faculty


def build_minimal_scope(*, section_strength=60, batch_strength=30, lab_capacity=35):
    college = College.objects.create(name="Test College", code="TST")
    ay = AcademicYear.objects.create(
        label="2099-2100", start_date=date(2099, 7, 1), end_date=date(2100, 5, 31), is_active=True
    )
    dept = Department.objects.create(college=college, code="CSE", name="Computer Science")

    calendar = AcademicCalendar.objects.create(
        academic_year=ay, department=None, semester_start=date(2099, 7, 15), semester_end=date(2099, 12, 1)
    )
    for day in Day:
        WorkingDay.objects.create(calendar=calendar, day=day, is_working=(day != Day.SATURDAY))

    year2 = Year.objects.create(department=dept, year_number=2, is_active=True)
    semester = Semester.objects.create(
        year=year2, academic_year=ay, semester_number=4, semester_type=SemesterType.EVEN, is_active=True
    )
    section = Section.objects.create(
        department=dept, year=year2, academic_year=ay, name="A", strength=section_strength
    )
    batch1 = Batch.objects.create(section=section, name="A1", strength=batch_strength)
    batch2 = Batch.objects.create(section=section, name="A2", strength=batch_strength)

    room1 = Classroom.objects.create(
        college=college, department=dept, room_number="CR-1", room_type=RoomType.CLASSROOM, capacity=70
    )
    room2 = Classroom.objects.create(
        college=college, department=dept, room_number="CR-2", room_type=RoomType.CLASSROOM, capacity=70
    )
    lab1 = Classroom.objects.create(
        college=college, department=dept, room_number="LAB-1", room_type=RoomType.LAB, capacity=lab_capacity
    )
    lab2 = Classroom.objects.create(
        college=college, department=dept, room_number="LAB-2", room_type=RoomType.LAB, capacity=lab_capacity
    )

    fac1 = Faculty.objects.create(
        department=dept, name="Dr. One", email="one@test.edu", short_code="ONE",
        max_lectures_per_day=6, max_lectures_per_week=24,
    )
    fac2 = Faculty.objects.create(
        department=dept, name="Dr. Two", email="two@test.edu", short_code="TWO",
        max_lectures_per_day=6, max_lectures_per_week=24,
    )

    dbms = Subject.objects.create(
        department=dept, year=year2, code="CS301", name="DBMS", lecture_hours=3, tutorial_hours=0,
        practical_hours=2, credits=4, category=SubjectCategory.CORE, has_batches=True, num_batches=2,
    )
    os_subject = Subject.objects.create(
        department=dept, year=year2, code="CS302", name="Operating Systems", lecture_hours=3,
        tutorial_hours=1, practical_hours=0, credits=4, category=SubjectCategory.CORE,
    )

    offering_dbms = SubjectOffering.objects.create(subject=dbms, section=section, semester=semester)
    offering_os = SubjectOffering.objects.create(subject=os_subject, section=section, semester=semester, faculty=fac2)

    return {
        "college": college, "academic_year": ay, "department": dept, "year": year2, "semester": semester,
        "section": section, "batch1": batch1, "batch2": batch2,
        "rooms": [room1, room2], "labs": [lab1, lab2],
        "faculty": [fac1, fac2],
        "subjects": [dbms, os_subject], "offerings": [offering_dbms, offering_os],
    }
