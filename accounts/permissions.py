"""
Backend-enforced permission classes.

Section 5 of the spec is explicit: "Never rely on hiding frontend buttons."
Every API view in the project must declare one of these (or compose them)
rather than trusting the client. Department isolation is enforced here,
not re-implemented per view.
"""

from rest_framework import permissions

from common.constants import Role


class IsSuperAdmin(permissions.BasePermission):
    message = "Only Super Admin can perform this action."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == Role.SUPER_ADMIN)


class IsSuperAdminOrDeptAdmin(permissions.BasePermission):
    message = "Only Super Admin or a Department Admin can perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in (Role.SUPER_ADMIN, Role.DEPT_ADMIN)
        )


class IsFaculty(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == Role.FACULTY)


class IsStudent(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == Role.STUDENT)


class ReadOnlyForStudentsAndFaculty(permissions.BasePermission):
    """Faculty/students may only ever perform safe (read) methods."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.role in (Role.SUPER_ADMIN, Role.DEPT_ADMIN):
            return True
        return request.method in permissions.SAFE_METHODS


class DepartmentScopedQuerysetMixin:
    """
    Mixin for DRF viewsets: Super Admin sees everything; Department Admin,
    Faculty and Student are restricted to their own department's data.
    `department_lookup` is the ORM path from the model to its Department
    (e.g. "department", "section__department", "subject__department").
    """

    department_lookup = "department"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_authenticated or user.role == Role.SUPER_ADMIN:
            return qs
        if user.department_id is None:
            return qs.none()
        return qs.filter(**{f"{self.department_lookup}_id": user.department_id})
