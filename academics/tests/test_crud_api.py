from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from academics.models import AcademicYear, College, Department, Section, Subject, Year
from common.constants import Role

User = get_user_model()


class AcademicsCrudTests(TestCase):
    def setUp(self):
        college = College.objects.create(name="T", code="T1")
        self.dept = Department.objects.create(college=college, code="CSE", name="CS")
        self.other_dept = Department.objects.create(college=college, code="ECE", name="EC")
        self.ay = AcademicYear.objects.create(label="2030-2031", start_date=date(2030, 7, 1), end_date=date(2031, 5, 31))
        self.year = Year.objects.create(department=self.dept, year_number=2)
        self.other_year = Year.objects.create(department=self.other_dept, year_number=2)

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

    # --- Subject CRUD -------------------------------------------------
    def test_super_admin_can_create_subject(self):
        resp = self.client.post(
            reverse("subject-list"),
            {"department": self.dept.id, "year": self.year.id, "code": "CS401", "name": "AI",
             "category": "CORE", "lecture_hours": 3, "tutorial_hours": 0, "practical_hours": 0, "credits": 3},
            content_type="application/json", **self._auth("super"),
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertTrue(Subject.objects.filter(code="CS401").exists())

    def test_faculty_cannot_create_subject(self):
        resp = self.client.post(
            reverse("subject-list"),
            {"department": self.dept.id, "year": self.year.id, "code": "CS402", "name": "ML"},
            content_type="application/json", **self._auth("fac"),
        )
        self.assertEqual(resp.status_code, 403)

    def test_odd_practical_hours_rejected_by_model_validation(self):
        subject = Subject(department=self.dept, year=self.year, code="CS500", name="Bad",
                           lecture_hours=2, practical_hours=3)
        with self.assertRaises(Exception):
            subject.full_clean()

    def test_odd_practical_hours_rejected_via_api(self):
        """Section 15: practicals must be 2-period blocks — enforced at
        the API layer too, not just the model and the frontend form."""
        resp = self.client.post(
            reverse("subject-list"),
            {"department": self.dept.id, "year": self.year.id, "code": "CS501", "name": "Odd Lab",
             "lecture_hours": 2, "practical_hours": 3},
            content_type="application/json", **self._auth("super"),
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(Subject.objects.filter(code="CS501").exists())

    def test_dept_admin_only_sees_own_department_subjects(self):
        Subject.objects.create(department=self.dept, year=self.year, code="CS410", name="A")
        Subject.objects.create(department=self.other_dept, year=self.other_year, code="EC410", name="B")

        resp = self.client.get(reverse("subject-list"), **self._auth("deptadmin"))
        self.assertEqual(resp.status_code, 200)
        codes = {s["code"] for s in resp.json()["results"]}
        self.assertEqual(codes, {"CS410"})

    def test_update_and_delete_subject(self):
        subj = Subject.objects.create(department=self.dept, year=self.year, code="CS420", name="Old Name")
        resp = self.client.patch(
            reverse("subject-detail", args=[subj.id]), {"name": "New Name"},
            content_type="application/json", **self._auth("super"),
        )
        self.assertEqual(resp.status_code, 200)
        subj.refresh_from_db()
        self.assertEqual(subj.name, "New Name")

        resp2 = self.client.delete(reverse("subject-detail", args=[subj.id]), **self._auth("super"))
        self.assertEqual(resp2.status_code, 204)
        self.assertFalse(Subject.objects.filter(id=subj.id).exists())

    def test_deactivated_subject_can_be_reactivated(self):
        """Regression test: the ViewSet's base queryset must not filter
        out inactive records, or a deactivated object becomes permanently
        invisible to its own detail endpoint and can never be turned back
        on via the API (found live: PATCH is_active=True 404'd after a
        prior PATCH is_active=False, because SubjectViewSet.queryset was
        `Subject.objects.filter(is_active=True)`)."""
        subj = Subject.objects.create(department=self.dept, year=self.year, code="CS430", name="Toggle Me")
        deactivate = self.client.patch(
            reverse("subject-detail", args=[subj.id]), {"is_active": False},
            content_type="application/json", **self._auth("super"),
        )
        self.assertEqual(deactivate.status_code, 200)

        # The object must still be independently fetchable and editable.
        fetch = self.client.get(reverse("subject-detail", args=[subj.id]), **self._auth("super"))
        self.assertEqual(fetch.status_code, 200)

        reactivate = self.client.patch(
            reverse("subject-detail", args=[subj.id]), {"is_active": True},
            content_type="application/json", **self._auth("super"),
        )
        self.assertEqual(reactivate.status_code, 200, reactivate.content)
        subj.refresh_from_db()
        self.assertTrue(subj.is_active)

    # --- Section CRUD ---------------------------------------------------
    def test_dept_admin_creating_section_is_forced_into_own_department(self):
        resp = self.client.post(
            reverse("section-list"),
            {"department": self.other_dept.id, "year": self.other_year.id, "academic_year": self.ay.id,
             "name": "Z", "strength": 50},
            content_type="application/json", **self._auth("deptadmin"),
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        section = Section.objects.get(name="Z")
        self.assertEqual(section.department_id, self.dept.id)  # NOT other_dept

    def test_section_list_is_readable_by_faculty(self):
        Section.objects.create(department=self.dept, year=self.year, academic_year=self.ay, name="A", strength=50)
        resp = self.client.get(reverse("section-list"), **self._auth("fac"))
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.json()["results"]), 1)
