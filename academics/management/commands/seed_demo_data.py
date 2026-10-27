"""
Creates a small, self-consistent demo dataset so the admin/faculty/student
portals and generator can be explored immediately after a fresh install.

Per Section 65 of the spec, this is deliberately kept in a management
command — a clearly separated dev fixture — and is never invoked by the
application itself. Re-running is safe (uses get_or_create throughout).
"""

from datetime import date

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

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
from common.constants import Day, RoomType, Role, SemesterType, SubjectCategory
from faculty.models import Faculty

User = get_user_model()


class Command(BaseCommand):
    help = "Seed a small demo dataset (college, departments, faculty, subjects, classrooms, sample users)."

    @transaction.atomic
    def handle(self, *args, **options):
        college, _ = College.objects.get_or_create(
            code="DEMO", defaults={"name": "Demo Institute of Technology"}
        )

        ay, _ = AcademicYear.objects.get_or_create(
            label="2026-2027",
            defaults={"start_date": date(2026, 7, 1), "end_date": date(2027, 5, 31), "is_active": True},
        )

        dept_cse, _ = Department.objects.get_or_create(college=college, code="CSE", defaults={"name": "Computer Science & Engineering"})
        dept_ece, _ = Department.objects.get_or_create(college=college, code="ECE", defaults={"name": "Electronics & Communication Engineering"})

        calendar, _ = AcademicCalendar.objects.get_or_create(
            academic_year=ay, department=None,
            defaults={"semester_start": date(2026, 7, 15), "semester_end": date(2026, 12, 5)},
        )
        for day in Day:
            WorkingDay.objects.get_or_create(
                calendar=calendar, day=day, defaults={"is_working": day != Day.SATURDAY}
            )

        rooms = []
        for i in range(1, 4):
            room, _ = Classroom.objects.get_or_create(
                college=college, room_number=f"CR-{200 + i}",
                defaults={"building": "Main Block", "room_type": RoomType.CLASSROOM, "capacity": 65, "department": dept_cse},
            )
            rooms.append(room)
        labs = []
        for i in range(1, 3):
            lab, _ = Classroom.objects.get_or_create(
                college=college, room_number=f"LAB-0{i}",
                defaults={"building": "Main Block", "room_type": RoomType.LAB, "capacity": 35, "department": dept_cse},
            )
            labs.append(lab)

        faculty_data = [
            ("Dr. Asha Rao", "asha.rao@demo.edu", "ARO", dept_cse),
            ("Dr. Vikram Nair", "vikram.nair@demo.edu", "VNR", dept_cse),
            ("Prof. Meera Iyer", "meera.iyer@demo.edu", "MIY", dept_cse),
        ]
        faculty_objs = []
        for name, email, code, dept in faculty_data:
            f, _ = Faculty.objects.get_or_create(
                email=email,
                defaults={"department": dept, "name": name, "short_code": code, "designation": "Assistant Professor"},
            )
            faculty_objs.append(f)

        year2_cse, _ = Year.objects.get_or_create(department=dept_cse, year_number=2, defaults={"is_active": True})
        for yn in (1, 3, 4):
            Year.objects.get_or_create(department=dept_cse, year_number=yn, defaults={"is_active": True})
        for yn in (1, 2, 3, 4):
            Year.objects.get_or_create(department=dept_ece, year_number=yn, defaults={"is_active": True})

        sem4, _ = Semester.objects.get_or_create(
            year=year2_cse, academic_year=ay, semester_number=4,
            defaults={"semester_type": SemesterType.EVEN, "is_active": True},
        )

        section_a, _ = Section.objects.get_or_create(
            department=dept_cse, year=year2_cse, academic_year=ay, name="A", defaults={"strength": 60}
        )
        batch1, _ = Batch.objects.get_or_create(section=section_a, name="A1", defaults={"strength": 30})
        batch2, _ = Batch.objects.get_or_create(section=section_a, name="A2", defaults={"strength": 30})

        subjects = [
            # code, name, lecture, tutorial, practical, category, has_batches
            ("CS301", "Database Management Systems", 3, 0, 2, SubjectCategory.CORE, True),
            ("CS302", "Operating Systems", 3, 1, 0, SubjectCategory.CORE, False),
            ("CS303", "Computer Networks", 3, 0, 0, SubjectCategory.CORE, False),
            ("CS304", "Soft Skills", 1, 0, 0, SubjectCategory.EXTRA, False),
        ]
        subject_objs = []
        for code, name, lec, tut, prac, cat, has_batches in subjects:
            s, _ = Subject.objects.get_or_create(
                department=dept_cse, year=year2_cse, code=code,
                defaults={"name": name, "lecture_hours": lec, "tutorial_hours": tut,
                          "practical_hours": prac, "credits": lec + tut + prac, "category": cat,
                          "has_batches": has_batches, "num_batches": 2 if has_batches else 1},
            )
            subject_objs.append(s)

        for i, subject in enumerate(subject_objs):
            SubjectOffering.objects.get_or_create(
                subject=subject, section=section_a, semester=sem4,
                defaults={"faculty": faculty_objs[i % len(faculty_objs)]},
            )

        demo_users = [
            ("dept_admin_cse", "DEPT_ADMIN", dept_cse, Role.DEPT_ADMIN),
            ("faculty_arao", "FACULTY", dept_cse, Role.FACULTY),
            ("student_demo", "STUDENT", dept_cse, Role.STUDENT),
        ]
        created_users = {}
        for username, _label, dept, role in demo_users:
            user, created = User.objects.get_or_create(
                username=username, defaults={"role": role, "department": dept, "email": f"{username}@demo.edu"}
            )
            if created:
                user.set_password("Demo@12345")
                user.save()
            created_users[username] = user

        # Link the demo login accounts to real domain records so the
        # faculty/student portals have something real to show.
        faculty_user = created_users["faculty_arao"]
        faculty_objs[0].user = faculty_user
        faculty_objs[0].save(update_fields=["user"])

        student_user = created_users["student_demo"]
        student_user.section = section_a
        student_user.save(update_fields=["section"])

        self.stdout.write(self.style.SUCCESS(
            "Demo data seeded: 1 college, 2 departments, 8 years, 1 semester, 1 section, "
            f"{len(faculty_objs)} faculty, {len(rooms) + len(labs)} rooms/labs, {len(subject_objs)} subjects, "
            "3 demo users (password: Demo@12345)."
        ))
