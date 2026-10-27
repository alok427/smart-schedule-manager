from rest_framework import permissions, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import DepartmentScopedQuerysetMixin, IsSuperAdminOrDeptAdmin
from common.constants import Role

from .models import AcademicYear, College, Department, Section, Semester, Subject, SubjectOffering, Year
from .serializers import (
    AcademicYearSerializer,
    CollegeSerializer,
    DepartmentSerializer,
    SectionSerializer,
    SemesterSerializer,
    SubjectOfferingSerializer,
    SubjectSerializer,
    YearSerializer,
)


class ReadOnlyBase(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated]


class CollegeViewSet(ReadOnlyBase):
    queryset = College.objects.all()
    serializer_class = CollegeSerializer


class AcademicYearViewSet(ReadOnlyBase):
    queryset = AcademicYear.objects.all()
    serializer_class = AcademicYearSerializer


class DepartmentViewSet(ReadOnlyBase):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == Role.SUPER_ADMIN:
            return qs
        return qs.filter(pk=user.department_id)


class YearViewSet(DepartmentScopedQuerysetMixin, ReadOnlyBase):
    queryset = Year.objects.all()
    serializer_class = YearSerializer
    filterset_fields = ["department", "is_active"]


class SemesterViewSet(ReadOnlyBase):
    queryset = Semester.objects.select_related("year", "academic_year").all()
    serializer_class = SemesterSerializer
    filterset_fields = ["year", "academic_year", "semester_type"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role != Role.SUPER_ADMIN:
            qs = qs.filter(year__department_id=user.department_id)
        return qs


class SectionViewSet(DepartmentScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = Section.objects.select_related("department", "year").all()
    serializer_class = SectionSerializer
    filterset_fields = ["department", "year", "academic_year"]

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


class SubjectViewSet(DepartmentScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    filterset_fields = ["department", "year", "category"]

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


class MyStudentTimetableView(APIView):
    """The logged-in STUDENT user's own class timetable (Section 6)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from common.constants import GenerationStatus, Role
        if request.user.role != Role.STUDENT:
            return Response({"detail": "Only student accounts have a class timetable."}, status=403)
        section = request.user.section
        if section is None:
            return Response({"detail": "No section is linked to your account yet. Contact your admin."}, status=404)

        semester = Semester.objects.filter(year=section.year, is_active=True).order_by("-academic_year__start_date").first()
        if semester is None:
            return Response({"detail": "No semester configured for your year yet.", "entries": []})

        from scheduling.models import TimetableEntry, TimetableVersion
        version = TimetableVersion.objects.filter(
            section=section, semester=semester, status=GenerationStatus.CURRENT
        ).first()
        if not version:
            return Response({
                "section": str(section), "entries": [],
                "detail": "No published timetable exists yet for your section.",
            })

        entries = (
            TimetableEntry.objects.filter(generation=version.generation, section=section)
            .select_related("session__subject_offering__subject", "faculty", "classroom", "batch")
            .order_by("day", "start_time")
        )
        data = [{
            "day": e.day, "period_label": e.period_label,
            "start_time": e.start_time, "end_time": e.end_time,
            "subject_code": e.session.subject_offering.subject.code,
            "subject_name": e.session.subject_offering.subject.name,
            "session_type": e.session.session_type,
            "faculty": e.faculty.name if e.faculty else None,
            "classroom": e.classroom.room_number if e.classroom else None,
            "batch": e.batch.name if e.batch else None,
        } for e in entries]
        return Response({"section": str(section), "version_number": version.version_number, "entries": data})


class SubjectOfferingViewSet(ReadOnlyBase):
    queryset = SubjectOffering.objects.select_related("subject", "faculty", "section", "semester").all()
    serializer_class = SubjectOfferingSerializer
    filterset_fields = ["section", "semester", "subject"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role != Role.SUPER_ADMIN:
            qs = qs.filter(section__department_id=user.department_id)
        return qs
