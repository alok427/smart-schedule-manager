from rest_framework import permissions, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import DepartmentScopedQuerysetMixin, IsSuperAdminOrDeptAdmin
from common.constants import GenerationStatus, Role

from .models import Faculty, FacultyAssignmentRule
from .serializers import FacultyAssignmentRuleSerializer, FacultySerializer


class FacultyViewSet(DepartmentScopedQuerysetMixin, viewsets.ModelViewSet):
    """Section 21: faculty configuration. Read is open to any authenticated
    user (needed for dropdowns); write is Super/Dept Admin only, and a Dept
    Admin can only create/edit faculty within their own department."""

    queryset = Faculty.objects.all()
    serializer_class = FacultySerializer
    filterset_fields = ["department", "faculty_type", "is_active"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.IsAuthenticated()]
        return [IsSuperAdminOrDeptAdmin()]

    def perform_create(self, serializer):
        user = self.request.user
        if user.role == Role.DEPT_ADMIN:
            serializer.save(department=user.department)
        else:
            serializer.save()

    def perform_update(self, serializer):
        user = self.request.user
        if user.role == Role.DEPT_ADMIN and serializer.instance.department_id != user.department_id:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Not authorized for this department.")
        serializer.save()


class FacultyAssignmentRuleViewSet(viewsets.ModelViewSet):
    """
    Section 20/21: Supporting/Additional/Restricted faculty eligibility
    rules. Read is open to authenticated users (the eligibility engine and
    UI dropdowns need to see them); write is Super/Dept Admin, scoped so a
    Dept Admin only manages rules for faculty in their own department.
    """

    queryset = FacultyAssignmentRule.objects.select_related("faculty", "department", "subject").all()
    serializer_class = FacultyAssignmentRuleSerializer
    filterset_fields = ["faculty", "department", "subject", "is_active", "is_generator_eligible"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.IsAuthenticated()]
        return [IsSuperAdminOrDeptAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_authenticated and user.role == Role.DEPT_ADMIN:
            qs = qs.filter(faculty__department_id=user.department_id)
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        faculty = serializer.validated_data.get("faculty")
        if user.role == Role.DEPT_ADMIN and faculty and faculty.department_id != user.department_id:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You can only create rules for faculty in your own department.")
        serializer.save()


class MyFacultyTimetableView(APIView):
    """The logged-in FACULTY user's own timetable, across every section
    they currently teach (Section 6: faculty see their weekly timetable)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if request.user.role != Role.FACULTY:
            return Response({"detail": "Only faculty accounts have a faculty timetable."}, status=403)
        faculty = getattr(request.user, "faculty_profile", None)
        if faculty is None:
            return Response({"detail": "No Faculty record is linked to your account yet. Contact your admin."}, status=404)

        from scheduling.services.current import current_entries
        entries = (
            current_entries().filter(faculty=faculty)
            .select_related("session__subject_offering__subject", "section", "classroom", "batch")
            .order_by("day", "start_time")
        )
        data = [{
            "day": e.day, "period_label": e.period_label,
            "start_time": e.start_time, "end_time": e.end_time,
            "subject_code": e.session.subject_offering.subject.code,
            "subject_name": e.session.subject_offering.subject.name,
            "session_type": e.session.session_type,
            "section": str(e.section),
            "classroom": e.classroom.room_number if e.classroom else None,
            "batch": e.batch.name if e.batch else None,
        } for e in entries]

        weekly_total = len(data)
        return Response({
            "faculty": {"name": faculty.name, "short_code": faculty.short_code,
                        "max_lectures_per_day": faculty.max_lectures_per_day,
                        "max_lectures_per_week": faculty.max_lectures_per_week},
            "weekly_total": weekly_total,
            "entries": data,
        })
