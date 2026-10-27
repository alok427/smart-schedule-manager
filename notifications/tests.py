from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from academics.models import College, Department
from common.constants import Role
from notifications.models import Notification, NotificationCategory

User = get_user_model()


class NotificationTests(TestCase):
    def setUp(self):
        college = College.objects.create(name="T", code="T1")
        dept = Department.objects.create(college=college, code="CSE", name="CS")
        self.user = User.objects.create_user(username="u1", password="Pass@1234", role=Role.DEPT_ADMIN, department=dept)
        self.other = User.objects.create_user(username="u2", password="Pass@1234", role=Role.DEPT_ADMIN, department=dept)

        Notification.objects.create(recipient=self.user, category=NotificationCategory.TIMETABLE_PUBLISHED, title="A")
        Notification.objects.create(recipient=self.user, category=NotificationCategory.TIMETABLE_PUBLISHED, title="B")
        Notification.objects.create(recipient=self.other, category=NotificationCategory.TIMETABLE_PUBLISHED, title="C")

    def _auth(self, username):
        resp = self.client.post(
            reverse("token_obtain_pair"), {"username": username, "password": "Pass@1234"},
            content_type="application/json",
        )
        return {"HTTP_AUTHORIZATION": f"Bearer {resp.json()['access']}"}

    def test_only_own_notifications_are_listed(self):
        resp = self.client.get(reverse("my_notifications"), **self._auth("u1"))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data["notifications"]), 2)
        self.assertEqual(data["unread_count"], 2)

    def test_mark_single_read(self):
        n = Notification.objects.filter(recipient=self.user).first()
        resp = self.client.post(reverse("mark_notification_read", args=[n.id]), **self._auth("u1"))
        self.assertEqual(resp.status_code, 200)
        n.refresh_from_db()
        self.assertTrue(n.is_read)

    def test_cannot_mark_someone_elses_notification_read(self):
        n = Notification.objects.filter(recipient=self.other).first()
        resp = self.client.post(reverse("mark_notification_read", args=[n.id]), **self._auth("u1"))
        self.assertEqual(resp.status_code, 404)
        n.refresh_from_db()
        self.assertFalse(n.is_read)

    def test_mark_all_read(self):
        resp = self.client.post(reverse("mark_all_notifications_read"), **self._auth("u1"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["marked_read"], 2)
        self.assertEqual(Notification.objects.filter(recipient=self.user, is_read=False).count(), 0)
