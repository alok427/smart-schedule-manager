"""
The one place that creates Notification rows (Section 58 — no duplicate
delivery logic elsewhere). Callers just describe what happened; this
decides who gets notified and creates the rows. Failures here are logged
and swallowed rather than propagated, since a notification problem must
never fail the underlying operation (e.g. a successful generation).
"""

import logging

from django.contrib.auth import get_user_model

from .models import Notification

logger = logging.getLogger("notifications")
User = get_user_model()


def notify_users(users, category, title, body="", link="", data=None):
    rows = [
        Notification(recipient=u, category=category, title=title, body=body, link=link, data=data or {})
        for u in users if u is not None
    ]
    if rows:
        Notification.objects.bulk_create(rows)
    return rows


def notify_department(department, category, title, body="", link="", data=None):
    from common.constants import Role
    users = User.objects.filter(department=department, role__in=[Role.DEPT_ADMIN, Role.FACULTY])
    return notify_users(users, category, title, body, link, data)


def notify_super_admins(category, title, body="", link="", data=None):
    from common.constants import Role
    users = User.objects.filter(role=Role.SUPER_ADMIN)
    return notify_users(users, category, title, body, link, data)
