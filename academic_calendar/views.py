from rest_framework import permissions, viewsets

from accounts.permissions import IsSuperAdminOrDeptAdmin
from common.constants import Role

from .models import AcademicCalendar, Event, Holiday, SpecialWorkingDay, WorkingDay
from .serializers import (
    AcademicCalendarSerializer,
    EventSerializer,
    HolidaySerializer,
    SpecialWorkingDaySerializer,
    WorkingDaySerializer,
)


class ScopedCalendarViewSet(viewsets.ModelViewSet):
    """Shared behaviour: read is open, write is Super/Dept Admin; a Dept
    Admin only sees/edits college-wide entries plus their own department's."""

    department_lookup = "calendar__department"

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.IsAuthenticated()]
        return [IsSuperAdminOrDeptAdmin()]

    def get_queryset(self):
        from django.db.models import Q
        qs = super().get_queryset()
        user = self.request.user
        if user.is_authenticated and user.role != Role.SUPER_ADMIN and user.department_id:
            qs = qs.filter(Q(**{f"{self.department_lookup}_id": user.department_id}) | Q(**{f"{self.department_lookup}__isnull": True}))
        return qs


class AcademicCalendarViewSet(viewsets.ModelViewSet):
    queryset = AcademicCalendar.objects.all()
    serializer_class = AcademicCalendarSerializer
    filterset_fields = ["academic_year", "department"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.IsAuthenticated()]
        return [IsSuperAdminOrDeptAdmin()]

    def get_queryset(self):
        from django.db.models import Q
        qs = super().get_queryset()
        user = self.request.user
        if user.is_authenticated and user.role != Role.SUPER_ADMIN and user.department_id:
            # College-wide (department=None) calendars are visible to
            # everyone; a department-specific calendar is only visible to
            # that department.
            qs = qs.filter(Q(department_id=user.department_id) | Q(department__isnull=True))
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        department = serializer.validated_data.get("department")
        if user.role == Role.DEPT_ADMIN:
            # Only Super Admin may create a college-wide calendar; a Dept
            # Admin is always forced into their own department's.
            serializer.save(department=user.department)
        else:
            serializer.save()

    def perform_update(self, serializer):
        user = self.request.user
        if user.role == Role.DEPT_ADMIN and serializer.instance.department_id != user.department_id:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Not authorized for this department's calendar.")
        serializer.save()


class WorkingDayViewSet(ScopedCalendarViewSet):
    queryset = WorkingDay.objects.select_related("calendar").all()
    serializer_class = WorkingDaySerializer
    filterset_fields = ["calendar", "day"]


class HolidayViewSet(ScopedCalendarViewSet):
    queryset = Holiday.objects.select_related("calendar").all()
    serializer_class = HolidaySerializer
    filterset_fields = ["calendar"]


class SpecialWorkingDayViewSet(ScopedCalendarViewSet):
    queryset = SpecialWorkingDay.objects.select_related("calendar").all()
    serializer_class = SpecialWorkingDaySerializer
    filterset_fields = ["calendar"]


class EventViewSet(ScopedCalendarViewSet):
    queryset = Event.objects.select_related("calendar").all()
    serializer_class = EventSerializer
    filterset_fields = ["calendar", "affects_timetable"]
