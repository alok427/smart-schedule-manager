import logging

from django.shortcuts import get_object_or_404
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from academics.models import AcademicYear, Department, Section, Year
from accounts.permissions import IsSuperAdminOrDeptAdmin
from common.constants import GenerationScopeType, GenerationStatus

from .models import FixedLecture, TimetableEntry, TimetableGeneration, TimetableVersion
from .serializers import (
    FixedLectureSerializer,
    GenerationCreateSerializer,
    TimetableEntryCellSerializer,
    TimetableGenerationSerializer,
    TimetableVersionSerializer,
)
from .services.generator import run_generation
from .services.versioning import restore_version

logger = logging.getLogger("scheduling")


class GenerateTimetableView(APIView):
    """
    Section 8: Generate Complete / Selected Section / Draft. Resolves the
    scope, creates the TimetableGeneration row, and runs the pipeline
    synchronously (small/medium college scale — see README for the note
    on moving this to an async task queue at larger scale).
    """

    permission_classes = [IsSuperAdminOrDeptAdmin]

    def post(self, request):
        serializer = GenerationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        academic_year = get_object_or_404(AcademicYear, pk=data["academic_year"])

        sections_qs = Section.objects.filter(academic_year=academic_year, is_active=True)
        user = request.user
        if user.role == "DEPT_ADMIN":
            sections_qs = sections_qs.filter(department=user.department)

        if data["scope_type"] == "SECTION":
            if not data["section_ids"]:
                return Response({"detail": "section_ids is required for SECTION scope."}, status=400)
            sections_qs = sections_qs.filter(id__in=data["section_ids"])
        else:
            if data["department_ids"]:
                sections_qs = sections_qs.filter(department_id__in=data["department_ids"])
            # Section 7: Year ON/OFF — only include active years, and if
            # the caller explicitly selected a subset, honour that too.
            sections_qs = sections_qs.filter(year__is_active=True)
            if data["year_numbers"]:
                sections_qs = sections_qs.filter(year__year_number__in=data["year_numbers"])

        sections = list(sections_qs.distinct())
        if not sections:
            return Response({"detail": "No active sections matched the requested scope."}, status=400)

        generation = TimetableGeneration.objects.create(
            academic_year=academic_year, semester_type=data["semester_type"],
            scope_type=data["scope_type"], status=GenerationStatus.PENDING,
            created_by=request.user,
        )
        generation.sections.set(sections)
        generation.departments.set({s.department for s in sections})
        generation.years.set({s.year for s in sections})

        try:
            run_generation(generation)
        except Exception:
            logger.exception("Generation #%s crashed unexpectedly.", generation.pk)
            generation.refresh_from_db()
            if generation.status not in (GenerationStatus.FAILED,):
                generation.status = GenerationStatus.FAILED
                generation.failure_summary = "An unexpected internal error occurred. See server logs."
                generation.save(update_fields=["status", "failure_summary"])

        generation.refresh_from_db()
        out = TimetableGenerationSerializer(generation).data
        http_status = status.HTTP_201_CREATED if generation.status != GenerationStatus.FAILED else status.HTTP_200_OK
        return Response(out, status=http_status)


class GenerationDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        generation = get_object_or_404(TimetableGeneration, pk=pk)
        return Response(TimetableGenerationSerializer(generation).data)


class ViewTimetableView(APIView):
    """
    Section 45: Department -> Semester -> Section -> View. Returns only
    the Current timetable for the requested section/semester — never a
    raw dump of all entries.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        section_id = request.query_params.get("section")
        semester_id = request.query_params.get("semester")
        if not section_id or not semester_id:
            return Response({"detail": "section and semester query params are required."}, status=400)

        section = get_object_or_404(Section, pk=section_id)
        user = request.user
        if user.role in ("DEPT_ADMIN", "FACULTY", "STUDENT") and user.department_id != section.department_id:
            return Response({"detail": "Not authorized for this department."}, status=403)

        version = TimetableVersion.objects.filter(
            section_id=section_id, semester_id=semester_id, status=GenerationStatus.CURRENT
        ).first()
        if not version:
            return Response({"detail": "No published (Current) timetable exists for this selection yet.", "entries": []})

        entries = (
            TimetableEntry.objects.filter(generation=version.generation, section_id=section_id)
            .select_related("session__subject_offering__subject", "faculty", "classroom", "batch")
            .order_by("day", "start_time")
        )
        return Response({
            "section": str(section),
            "version_number": version.version_number,
            "activated_at": version.activated_at,
            "entries": TimetableEntryCellSerializer(entries, many=True).data,
        })


class TimetableHistoryView(APIView):
    """Section 40: history, with the last 3 versions per section prominently
    accessible; older versions remain queryable, never deleted."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        section_id = request.query_params.get("section")
        semester_id = request.query_params.get("semester")
        if not section_id or not semester_id:
            return Response({"detail": "section and semester query params are required."}, status=400)

        versions = TimetableVersion.objects.filter(
            section_id=section_id, semester_id=semester_id
        ).order_by("-version_number")
        recent = versions[:3]
        return Response({
            "recent": TimetableVersionSerializer(recent, many=True).data,
            "total_versions": versions.count(),
        })


class RestoreVersionView(APIView):
    """Section 41/78: activate an exact saved version. Never regenerates."""

    permission_classes = [IsSuperAdminOrDeptAdmin]

    def post(self, request, pk):
        version = get_object_or_404(TimetableVersion, pk=pk)
        if request.user.role == "DEPT_ADMIN" and request.user.department_id != version.section.department_id:
            return Response({"detail": "Not authorized for this department."}, status=403)

        result = restore_version(version, actor=request.user)
        if not result.is_valid:
            return Response({"detail": "Restore blocked by conflicts.", "violations": result.violations}, status=409)
        return Response(TimetableVersionSerializer(version).data)


class FixedLectureViewSet(viewsets.ModelViewSet):
    """Section 27: admin-managed fixed/locked lectures."""

    queryset = FixedLecture.objects.select_related("subject_offering", "faculty", "classroom").all()
    serializer_class = FixedLectureSerializer
    permission_classes = [IsSuperAdminOrDeptAdmin]
    filterset_fields = ["subject_offering", "subject_offering__section", "subject_offering__semester", "is_active"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == "DEPT_ADMIN":
            qs = qs.filter(subject_offering__section__department=user.department)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class MoveSessionView(APIView):
    """Section 43: change slot (also covers moving a 2-period lab block as
    a unit). Validated immediately via the central validation service."""

    permission_classes = [IsSuperAdminOrDeptAdmin]

    def post(self, request):
        from academics.models import Section
        from .models import TimetableSession
        from .serializers import MoveSessionSerializer
        from .services.manual_edit import move_session

        serializer = MoveSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        session = get_object_or_404(TimetableSession, pk=data["session_id"])
        section = session.subject_offering.section
        if request.user.role == "DEPT_ADMIN" and request.user.department_id != section.department_id:
            return Response({"detail": "Not authorized for this department."}, status=403)

        result = move_session(session, new_day=data["new_day"], new_period_labels=data["new_period_labels"],
                               actor=request.user)
        if not result.is_valid:
            return Response({"detail": "Move rejected.", "violations": result.violations}, status=409)
        return Response({"detail": "Moved successfully."})


class ChangeClassroomView(APIView):
    """Section 43: change classroom."""

    permission_classes = [IsSuperAdminOrDeptAdmin]

    def post(self, request):
        from classrooms.models import Classroom
        from .models import TimetableSession
        from .serializers import ChangeClassroomSerializer
        from .services.manual_edit import change_classroom_for_session

        serializer = ChangeClassroomSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        session = get_object_or_404(TimetableSession, pk=data["session_id"])
        new_classroom = get_object_or_404(Classroom, pk=data["new_classroom_id"])
        section = session.subject_offering.section
        if request.user.role == "DEPT_ADMIN" and request.user.department_id != section.department_id:
            return Response({"detail": "Not authorized for this department."}, status=403)

        result = change_classroom_for_session(session, new_classroom=new_classroom, actor=request.user)
        if not result.is_valid:
            return Response({"detail": "Room change rejected.", "violations": result.violations}, status=409)
        return Response({"detail": "Room changed successfully."})


class ChangeFacultyView(APIView):
    """Section 33/43: faculty override — changes ALL sessions for the
    subject offering, or is entirely rejected."""

    permission_classes = [IsSuperAdminOrDeptAdmin]

    def post(self, request):
        from academics.models import SubjectOffering
        from faculty.models import Faculty
        from .serializers import ChangeFacultySerializer
        from .services.manual_edit import change_faculty_for_offering

        serializer = ChangeFacultySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        offering = get_object_or_404(SubjectOffering, pk=data["offering_id"])
        new_faculty = get_object_or_404(Faculty, pk=data["new_faculty_id"])
        if request.user.role == "DEPT_ADMIN" and request.user.department_id != offering.section.department_id:
            return Response({"detail": "Not authorized for this department."}, status=403)

        result = change_faculty_for_offering(offering, new_faculty=new_faculty, actor=request.user)
        if not result.is_valid:
            return Response({"detail": "Faculty change rejected.", "violations": result.violations}, status=409)
        return Response({"detail": "Faculty changed successfully."})
