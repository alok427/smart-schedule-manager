from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from common.constants import GenerationStatus, Role
from scheduling.services.generator import run_generation
from scheduling.tests.factories import build_minimal_scope
from scheduling.tests.test_generation import _create_generation

User = get_user_model()


class DashboardTests(TestCase):
    def setUp(self):
        self.scope = build_minimal_scope()
        gen = _create_generation(self.scope)
        run_generation(gen)
        self.assertEqual(gen.status, GenerationStatus.CURRENT)

        self.admin = User.objects.create_user(
            username="super", password="Pass@1234", role=Role.SUPER_ADMIN, is_staff=True, is_superuser=True,
        )
        self.dept_admin = User.objects.create_user(
            username="deptadmin", password="Pass@1234", role=Role.DEPT_ADMIN, department=self.scope["department"],
        )

    def _auth(self, username):
        resp = self.client.post(
            reverse("token_obtain_pair"), {"username": username, "password": "Pass@1234"},
            content_type="application/json",
        )
        return {"HTTP_AUTHORIZATION": f"Bearer {resp.json()['access']}"}

    def test_dashboard_stats_reflects_seeded_scope(self):
        resp = self.client.get(reverse("dashboard_stats"), **self._auth("super"))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["faculty_count"], 2)
        self.assertEqual(data["subject_count"], 2)
        self.assertEqual(data["lab_count"], 2)

    def test_search_finds_subject_by_code(self):
        resp = self.client.get(reverse("global_search"), {"q": "CS301"}, **self._auth("super"))
        self.assertEqual(resp.status_code, 200)
        codes = [s["code"] for s in resp.json()["subjects"]]
        self.assertIn("CS301", codes)

    def test_search_requires_query(self):
        resp = self.client.get(reverse("global_search"), **self._auth("super"))
        self.assertEqual(resp.status_code, 400)
