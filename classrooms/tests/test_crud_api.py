from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from academics.models import College, Department
from classrooms.models import Classroom
from common.constants import Role

User = get_user_model()


class ClassroomCrudTests(TestCase):
    def setUp(self):
        self.college = College.objects.create(name="T", code="T1")
        self.dept = Department.objects.create(college=self.college, code="CSE", name="CS")
        self.other_college = College.objects.create(name="T2", code="T2")
        self.other_dept = Department.objects.create(college=self.other_college, code="MECH", name="ME")

        self.super_admin = User.objects.create_user(
            username="super", password="Pass@1234", role=Role.SUPER_ADMIN, is_staff=True, is_superuser=True,
        )
        self.dept_admin = User.objects.create_user(
            username="deptadmin", password="Pass@1234", role=Role.DEPT_ADMIN, department=self.dept,
        )

    def _auth(self, username):
        resp = self.client.post(
            reverse("token_obtain_pair"), {"username": username, "password": "Pass@1234"},
            content_type="application/json",
        )
        return {"HTTP_AUTHORIZATION": f"Bearer {resp.json()['access']}"}

    def test_college_is_server_derived_from_department_not_client_supplied(self):
        """The frontend form never sends `college` — it must be derived
        from the chosen department, and a client-supplied value must be
        ignored rather than trusted (Section 61: never trust client input
        for authorization-relevant fields)."""
        resp = self.client.post(
            reverse("classroom-list"),
            {"department": self.dept.id, "room_number": "CR-900", "room_type": "CLASSROOM",
             "capacity": 50, "college": self.other_college.id},  # attempted override, must be ignored
            content_type="application/json", **self._auth("super"),
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        room = Classroom.objects.get(room_number="CR-900")
        self.assertEqual(room.college_id, self.college.id)  # derived from dept, NOT other_college

    def test_shared_room_with_no_department_uses_requesters_college(self):
        resp = self.client.post(
            reverse("classroom-list"),
            {"room_number": "CR-901", "room_type": "CLASSROOM", "capacity": 50},
            content_type="application/json", **self._auth("deptadmin"),
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        room = Classroom.objects.get(room_number="CR-901")
        self.assertEqual(room.college_id, self.college.id)

    def test_dept_admin_is_forced_into_own_department(self):
        resp = self.client.post(
            reverse("classroom-list"),
            {"department": self.other_dept.id, "room_number": "CR-902", "room_type": "LAB", "capacity": 30},
            content_type="application/json", **self._auth("deptadmin"),
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        room = Classroom.objects.get(room_number="CR-902")
        self.assertEqual(room.department_id, self.dept.id)  # NOT other_dept
        self.assertEqual(room.college_id, self.college.id)

    def test_update_classroom_capacity(self):
        room = Classroom.objects.create(college=self.college, department=self.dept, room_number="CR-903",
                                         room_type="CLASSROOM", capacity=40)
        resp = self.client.patch(
            reverse("classroom-detail", args=[room.id]), {"capacity": 60},
            content_type="application/json", **self._auth("super"),
        )
        self.assertEqual(resp.status_code, 200)
        room.refresh_from_db()
        self.assertEqual(room.capacity, 60)

    def test_delete_classroom(self):
        room = Classroom.objects.create(college=self.college, department=self.dept, room_number="CR-904",
                                         room_type="CLASSROOM", capacity=40)
        resp = self.client.delete(reverse("classroom-detail", args=[room.id]), **self._auth("super"))
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Classroom.objects.filter(id=room.id).exists())
