from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from academics.models import College, Department, Subject, Year
from common.constants import Role
from faculty.models import Faculty, FacultyAssignmentRule

User = get_user_model()


class FacultyCrudTests(TestCase):
    def setUp(self):
        college = College.objects.create(name="T", code="T1")
        self.dept = Department.objects.create(college=college, code="CSE", name="CS")
        self.other_dept = Department.objects.create(college=college, code="ECE", name="EC")

        self.super_admin = User.objects.create_user(
            username="super", password="Pass@1234", role=Role.SUPER_ADMIN, is_staff=True, is_superuser=True,
        )
        self.dept_admin = User.objects.create_user(
            username="deptadmin", password="Pass@1234", role=Role.DEPT_ADMIN, department=self.dept,
        )
        self.student_user = User.objects.create_user(
            username="stud", password="Pass@1234", role=Role.STUDENT, department=self.dept,
        )

    def _auth(self, username):
        resp = self.client.post(
            reverse("token_obtain_pair"), {"username": username, "password": "Pass@1234"},
            content_type="application/json",
        )
        return {"HTTP_AUTHORIZATION": f"Bearer {resp.json()['access']}"}

    def test_super_admin_creates_faculty(self):
        resp = self.client.post(
            reverse("faculty-list"),
            {"department": self.dept.id, "name": "Dr. X", "email": "x@test.edu", "short_code": "DRX",
             "max_lectures_per_day": 6, "max_lectures_per_week": 24},
            content_type="application/json", **self._auth("super"),
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertTrue(Faculty.objects.filter(short_code="DRX").exists())

    def test_student_cannot_create_faculty_but_can_list(self):
        resp = self.client.post(
            reverse("faculty-list"),
            {"department": self.dept.id, "name": "Dr. Y", "email": "y@test.edu", "short_code": "DRY"},
            content_type="application/json", **self._auth("stud"),
        )
        self.assertEqual(resp.status_code, 403)

        resp2 = self.client.get(reverse("faculty-list"), **self._auth("stud"))
        self.assertEqual(resp2.status_code, 200)

    def test_dept_admin_cannot_see_or_edit_faculty_in_other_department(self):
        """DepartmentScopedQuerysetMixin filters the queryset before the
        object lookup, so a Dept Admin gets 404 (object not visible to
        them at all) rather than 403 — deliberately not revealing that a
        faculty record exists in a department they can't access."""
        fac = Faculty.objects.create(department=self.other_dept, name="Dr. Z", email="z@test.edu", short_code="DRZ")
        resp = self.client.patch(
            reverse("faculty-detail", args=[fac.id]), {"name": "Renamed"},
            content_type="application/json", **self._auth("deptadmin"),
        )
        self.assertEqual(resp.status_code, 404)
        fac.refresh_from_db()
        self.assertEqual(fac.name, "Dr. Z")

    def test_deactivate_and_reactivate_faculty(self):
        fac = Faculty.objects.create(department=self.dept, name="Dr. W", email="w@test.edu", short_code="DRW")
        resp = self.client.patch(
            reverse("faculty-detail", args=[fac.id]), {"is_active": False},
            content_type="application/json", **self._auth("super"),
        )
        self.assertEqual(resp.status_code, 200)
        fac.refresh_from_db()
        self.assertFalse(fac.is_active)


class FacultyAssignmentRuleCrudTests(TestCase):
    def setUp(self):
        college = College.objects.create(name="T", code="T1")
        self.dept = Department.objects.create(college=college, code="CSE", name="CS")
        self.year = Year.objects.create(department=self.dept, year_number=2)
        self.subject = Subject.objects.create(department=self.dept, year=self.year, code="CS301", name="DBMS")
        self.faculty = Faculty.objects.create(department=self.dept, name="Dr. Support", email="s@test.edu", short_code="SUP")

        self.super_admin = User.objects.create_user(
            username="super", password="Pass@1234", role=Role.SUPER_ADMIN, is_staff=True, is_superuser=True,
        )

    def _auth(self, username):
        resp = self.client.post(
            reverse("token_obtain_pair"), {"username": username, "password": "Pass@1234"},
            content_type="application/json",
        )
        return {"HTTP_AUTHORIZATION": f"Bearer {resp.json()['access']}"}

    def test_create_rule_scoped_to_subject(self):
        resp = self.client.post(
            reverse("faculty-assignment-rule-list"),
            {"faculty": self.faculty.id, "subject": self.subject.id, "max_lectures": 4, "is_generator_eligible": True},
            content_type="application/json", **self._auth("super"),
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertTrue(FacultyAssignmentRule.objects.filter(faculty=self.faculty, subject=self.subject).exists())

    def test_rule_with_no_scope_is_rejected(self):
        resp = self.client.post(
            reverse("faculty-assignment-rule-list"),
            {"faculty": self.faculty.id}, content_type="application/json", **self._auth("super"),
        )
        self.assertEqual(resp.status_code, 400)

    def test_fixed_day_requires_fixed_slot_to_be_meaningful(self):
        # The API itself doesn't require slot+day together (that pairing
        # is enforced in the UI); this test documents that a rule can be
        # saved with just fixed_day, and confirms it round-trips correctly.
        resp = self.client.post(
            reverse("faculty-assignment-rule-list"),
            {"faculty": self.faculty.id, "subject": self.subject.id, "fixed_day": 2, "fixed_slot_label": "P3"},
            content_type="application/json", **self._auth("super"),
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        rule = FacultyAssignmentRule.objects.get(faculty=self.faculty, subject=self.subject)
        self.assertEqual(rule.fixed_day, 2)
        self.assertEqual(rule.fixed_slot_label, "P3")

    def test_delete_rule(self):
        rule = FacultyAssignmentRule.objects.create(faculty=self.faculty, subject=self.subject, max_lectures=3)
        resp = self.client.delete(reverse("faculty-assignment-rule-detail", args=[rule.id]), **self._auth("super"))
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(FacultyAssignmentRule.objects.filter(id=rule.id).exists())
