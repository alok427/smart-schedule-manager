from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from academic_calendar.models import AcademicCalendar, Holiday, WorkingDay
from academics.models import AcademicYear, College, Department
from common.constants import Role

User = get_user_model()


class AcademicCalendarCrudTests(TestCase):
    def setUp(self):
        college = College.objects.create(name="T", code="T1")
        self.dept = Department.objects.create(college=college, code="CSE", name="CS")
        self.other_dept = Department.objects.create(college=college, code="ECE", name="EC")
        self.ay = AcademicYear.objects.create(label="2030-2031", start_date=date(2030, 7, 1), end_date=date(2031, 5, 31))

        self.super_admin = User.objects.create_user(
            username="super", password="Pass@1234", role=Role.SUPER_ADMIN, is_staff=True, is_superuser=True,
        )
        self.dept_admin = User.objects.create_user(
            username="deptadmin", password="Pass@1234", role=Role.DEPT_ADMIN, department=self.dept,
        )
        self.faculty_user = User.objects.create_user(
            username="fac", password="Pass@1234", role=Role.FACULTY, department=self.dept,
        )

    def _auth(self, username):
        resp = self.client.post(
            reverse("token_obtain_pair"), {"username": username, "password": "Pass@1234"},
            content_type="application/json",
        )
        return {"HTTP_AUTHORIZATION": f"Bearer {resp.json()['access']}"}

    def test_create_college_wide_calendar(self):
        resp = self.client.post(
            reverse("academic-calendar-list"),
            {"academic_year": self.ay.id, "department": None, "semester_start": "2030-07-15", "semester_end": "2030-12-05"},
            content_type="application/json", **self._auth("super"),
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertTrue(AcademicCalendar.objects.filter(academic_year=self.ay, department=None).exists())

    def test_faculty_cannot_create_calendar_but_can_read(self):
        resp = self.client.post(
            reverse("academic-calendar-list"),
            {"academic_year": self.ay.id, "semester_start": "2030-07-15", "semester_end": "2030-12-05"},
            content_type="application/json", **self._auth("fac"),
        )
        self.assertEqual(resp.status_code, 403)

        AcademicCalendar.objects.create(academic_year=self.ay, semester_start=date(2030, 7, 15), semester_end=date(2030, 12, 5))
        resp2 = self.client.get(reverse("academic-calendar-list"), **self._auth("fac"))
        self.assertEqual(resp2.status_code, 200)

    def test_toggle_working_day(self):
        calendar = AcademicCalendar.objects.create(
            academic_year=self.ay, semester_start=date(2030, 7, 15), semester_end=date(2030, 12, 5),
        )
        wd = WorkingDay.objects.create(calendar=calendar, day=5, is_working=False)  # Saturday off by default
        resp = self.client.patch(
            reverse("working-day-detail", args=[wd.id]), {"is_working": True},
            content_type="application/json", **self._auth("super"),
        )
        self.assertEqual(resp.status_code, 200)
        wd.refresh_from_db()
        self.assertTrue(wd.is_working)

    def test_add_and_list_holiday(self):
        calendar = AcademicCalendar.objects.create(
            academic_year=self.ay, semester_start=date(2030, 7, 15), semester_end=date(2030, 12, 5),
        )
        resp = self.client.post(
            reverse("holiday-list"),
            {"calendar": calendar.id, "date": "2030-10-02", "name": "Gandhi Jayanti"},
            content_type="application/json", **self._auth("super"),
        )
        self.assertEqual(resp.status_code, 201, resp.content)

        resp2 = self.client.get(f"{reverse('holiday-list')}?calendar={calendar.id}", **self._auth("fac"))
        self.assertEqual(resp2.status_code, 200)
        names = {h["name"] for h in resp2.json()["results"]}
        self.assertIn("Gandhi Jayanti", names)

    def test_duplicate_holiday_same_date_rejected(self):
        calendar = AcademicCalendar.objects.create(
            academic_year=self.ay, semester_start=date(2030, 7, 15), semester_end=date(2030, 12, 5),
        )
        Holiday.objects.create(calendar=calendar, date=date(2030, 10, 2), name="Gandhi Jayanti")
        resp = self.client.post(
            reverse("holiday-list"),
            {"calendar": calendar.id, "date": "2030-10-02", "name": "Duplicate"},
            content_type="application/json", **self._auth("super"),
        )
        self.assertEqual(resp.status_code, 400)

    def test_dept_admin_only_sees_college_wide_and_own_department_calendars(self):
        AcademicCalendar.objects.create(academic_year=self.ay, department=None,
                                         semester_start=date(2030, 7, 15), semester_end=date(2030, 12, 5))
        AcademicCalendar.objects.create(academic_year=self.ay, department=self.dept,
                                         semester_start=date(2030, 7, 15), semester_end=date(2030, 12, 5))
        AcademicCalendar.objects.create(academic_year=self.ay, department=self.other_dept,
                                         semester_start=date(2030, 7, 15), semester_end=date(2030, 12, 5))

        resp = self.client.get(reverse("academic-calendar-list"), **self._auth("deptadmin"))
        self.assertEqual(resp.status_code, 200)
        seen_depts = {c["department"] for c in resp.json()["results"]}
        self.assertEqual(seen_depts, {None, self.dept.id})  # NOT other_dept

    def test_dept_admin_creating_calendar_is_forced_into_own_department(self):
        """Even if a Dept Admin submits department=<other dept> (or tries
        to create a college-wide one by omitting it), the server forces
        it to their own department — never trust client-supplied scope
        for an authorization-relevant field."""
        resp = self.client.post(
            reverse("academic-calendar-list"),
            {"academic_year": self.ay.id, "department": self.other_dept.id,
             "semester_start": "2030-07-15", "semester_end": "2030-12-05"},
            content_type="application/json", **self._auth("deptadmin"),
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        calendar = AcademicCalendar.objects.get(academic_year=self.ay, department=self.dept)
        self.assertNotEqual(calendar.department_id, self.other_dept.id)

    def test_dept_admin_cannot_edit_other_departments_calendar(self):
        calendar = AcademicCalendar.objects.create(
            academic_year=self.ay, department=self.other_dept,
            semester_start=date(2030, 7, 15), semester_end=date(2030, 12, 5),
        )
        resp = self.client.patch(
            reverse("academic-calendar-detail", args=[calendar.id]), {"semester_end": "2030-12-20"},
            content_type="application/json", **self._auth("deptadmin"),
        )
        self.assertEqual(resp.status_code, 404)  # not visible to them at all
        calendar.refresh_from_db()
        self.assertEqual(str(calendar.semester_end), "2030-12-05")
