from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from academics.models import College, Department
from common.constants import Role

User = get_user_model()


class AuthAndPermissionTests(TestCase):
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
        self.faculty_user = User.objects.create_user(
            username="fac", password="Pass@1234", role=Role.FACULTY, department=self.dept,
        )
        self.student_user = User.objects.create_user(
            username="stud", password="Pass@1234", role=Role.STUDENT, department=self.dept,
        )

    def _login(self, username, password="Pass@1234"):
        resp = self.client.post(
            reverse("token_obtain_pair"), {"username": username, "password": password},
            content_type="application/json",
        )
        return resp

    def _auth(self, username):
        resp = self._login(username)
        token = resp.json()["access"]
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_login_succeeds_with_correct_password(self):
        resp = self._login("super")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("access", resp.json())
        self.assertEqual(resp.json()["role"], "SUPER_ADMIN")

    def test_login_fails_with_wrong_password(self):
        resp = self._login("super", password="wrong")
        self.assertEqual(resp.status_code, 401)

    def test_me_endpoint_requires_auth(self):
        resp = self.client.get(reverse("me"))
        self.assertEqual(resp.status_code, 401)

    def test_me_endpoint_returns_correct_user(self):
        resp = self.client.get(reverse("me"), **self._auth("fac"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["username"], "fac")
        self.assertEqual(resp.json()["role"], "FACULTY")

    def test_faculty_cannot_list_users(self):
        resp = self.client.get(reverse("user-list"), **self._auth("fac"))
        self.assertEqual(resp.status_code, 403)

    def test_student_cannot_list_users(self):
        resp = self.client.get(reverse("user-list"), **self._auth("stud"))
        self.assertEqual(resp.status_code, 403)

    def test_super_admin_can_list_all_users(self):
        resp = self.client.get(reverse("user-list"), **self._auth("super"))
        self.assertEqual(resp.status_code, 200)
        usernames = {u["username"] for u in resp.json()["results"]}
        self.assertIn("deptadmin", usernames)
        self.assertIn("fac", usernames)

    def test_dept_admin_only_sees_own_department_users(self):
        resp = self.client.get(reverse("user-list"), **self._auth("deptadmin"))
        self.assertEqual(resp.status_code, 200)
        depts = {u["department"] for u in resp.json()["results"]}
        self.assertEqual(depts, {self.dept.id})

    def test_dept_admin_cannot_create_super_admin(self):
        resp = self.client.post(
            reverse("user-list"),
            {"username": "newsuper", "password": "Complex@Pass1", "role": "SUPER_ADMIN",
             "email": "x@example.com", "department": self.dept.id},
            **self._auth("deptadmin"),
        )
        self.assertEqual(resp.status_code, 403)

    def test_dept_admin_created_user_is_forced_into_their_department(self):
        resp = self.client.post(
            reverse("user-list"),
            {"username": "newfac", "password": "Complex@Pass1", "role": "FACULTY",
             "email": "y@example.com", "department": self.other_dept.id},
            **self._auth("deptadmin"),
        )
        self.assertEqual(resp.status_code, 201)
        created = User.objects.get(username="newfac")
        self.assertEqual(created.department_id, self.dept.id)  # NOT other_dept, despite what was submitted


class LoginThrottleTests(TestCase):
    """
    Section 61 security: the login endpoint must throttle repeated
    attempts. Isolated from the rest of the suite via override_settings
    (a real, tight rate) and an explicit cache clear, since DRF's
    throttle cache is process-wide and would otherwise leak between
    tests that legitimately log in more than once.
    """

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        User.objects.create_user(username="throttleuser", password="Pass@1234", role=Role.STUDENT)

    def tearDown(self):
        from django.core.cache import cache
        cache.clear()

    def test_repeated_failed_logins_are_throttled(self):
        from unittest.mock import patch

        from rest_framework.throttling import ScopedRateThrottle

        # DRF's throttle classes bind THROTTLE_RATES from api_settings at
        # class-definition (import) time, not per-request — so
        # override_settings(REST_FRAMEWORK=...) alone won't reliably
        # change it here. Patching the class attribute directly is the
        # reliable way to exercise a tight rate in an isolated test.
        with patch.object(ScopedRateThrottle, "THROTTLE_RATES", {"login": "3/minute"}):
            statuses = []
            for _ in range(5):
                resp = self.client.post(
                    reverse("token_obtain_pair"), {"username": "throttleuser", "password": "wrong"},
                    content_type="application/json",
                )
                statuses.append(resp.status_code)

        self.assertIn(401, statuses[:3])  # first attempts are genuinely evaluated (wrong password)
        self.assertIn(429, statuses)      # later attempts get throttled, not evaluated at all
        self.assertEqual(statuses[-1], 429)

