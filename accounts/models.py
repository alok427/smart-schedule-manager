from django.contrib.auth.models import AbstractUser
from django.db import models

from common.constants import Role
from common.models import TimeStampedModel


class User(AbstractUser, TimeStampedModel):
    """
    Custom user model. Role drives what a person can see/do; enforcement
    happens in DRF permission classes (accounts.permissions), never just in
    the frontend (see Section 5 of the spec).

    `department` scopes DEPT_ADMIN/FACULTY/STUDENT users to a single
    department. SUPER_ADMIN users should leave it null (full access).
    Referenced by string to avoid a circular import with `academics`.
    """

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)
    department = models.ForeignKey(
        "academics.Department",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="users",
    )
    section = models.ForeignKey(
        "academics.Section",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="students",
        help_text="Only meaningful for STUDENT accounts — which class/section timetable they see.",
    )
    phone_number = models.CharField(max_length=20, blank=True)
    must_change_password = models.BooleanField(
        default=False,
        help_text="Force password change on next login (e.g. after admin-created account).",
    )

    class Meta:
        indexes = [
            models.Index(fields=["role"]),
            models.Index(fields=["department"]),
        ]

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    @property
    def is_super_admin(self):
        return self.role == Role.SUPER_ADMIN

    @property
    def is_dept_admin(self):
        return self.role == Role.DEPT_ADMIN

    @property
    def is_faculty_role(self):
        return self.role == Role.FACULTY

    @property
    def is_student_role(self):
        return self.role == Role.STUDENT
