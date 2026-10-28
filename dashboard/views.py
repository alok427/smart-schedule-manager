"""
Section 49: admin dashboard counts + conflicts/warnings + Section 59
global search. Department Admins are scoped to their own department;
Super Admins see everything.
"""

from django.db.models import Q
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsSuperAdminOrDeptAdmin
from academics.models import Department, Section, Subject
from classrooms.models import Classroom
from common.constants import GenerationStatus, Role
from faculty.models import Faculty
from scheduling.models import GenerationIssue, TimetableGeneration


class DashboardStatsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        dept_filter = {} if user.role == Role.SUPER_ADMIN else {"department": user.department}

        faculty_qs = Faculty.objects.filter(**({"department": user.department} if dept_filter else {}))
        subject_qs = Subject.objects.filter(**dept_filter)
        classroom_qs = Classroom.objects.filter(**dept_filter) if dept_filter else Classroom.objects.all()
        section_qs = Section.objects.filter(**dept_filter)
        department_qs = Department.objects.all() if user.role == Role.SUPER_ADMIN else Department.objects.filter(
            pk=user.department_id
        )

        recent_issues = GenerationIssue.objects.filter(severity="ERROR")
        if dept_filter:
            recent_issues = recent_issues.filter(section__department=user.department)
        recent_issues = recent_issues.select_related("section", "subject").order_by("-created_at")[:20]

        stale_generations = TimetableGeneration.objects.filter(status=GenerationStatus.FAILED)
        if dept_filter:
            stale_generations = stale_generations.filter(departments=user.department)

        return Response({
            "faculty_count": faculty_qs.count(),
            "student_count": None,  # Section 49 — no Student roster model exists yet beyond User accounts.
            "department_count": department_qs.count(),
            "section_count": section_qs.count(),
            "subject_count": subject_qs.count(),
            "classroom_count": classroom_qs.filter(room_type="CLASSROOM").count(),
            "lab_count": classroom_qs.filter(room_type="LAB").count(),
            "failed_generation_count": stale_generations.count(),
            "recent_conflicts": [
                {
                    "id": i.id,
                    "section": str(i.section),
                    "subject": str(i.subject) if i.subject else None,
                    "message": i.message,
                }
                for i in recent_issues
            ],
        })


class DeleteConflictView(APIView):
    """Dismiss one conflict/warning from the dashboard (Dept Admin: own department only)."""

    permission_classes = [IsSuperAdminOrDeptAdmin]

    def post(self, request, pk):
        qs = GenerationIssue.objects.filter(pk=pk, severity="ERROR")
        if request.user.role != Role.SUPER_ADMIN:
            qs = qs.filter(section__department=request.user.department)
        deleted, _ = qs.delete()
        if not deleted:
            return Response({"detail": "Not found."}, status=404)
        return Response({"deleted": deleted})


class ClearConflictsView(APIView):
    """Clear all conflicts/warnings visible to this admin."""

    permission_classes = [IsSuperAdminOrDeptAdmin]

    def post(self, request):
        qs = GenerationIssue.objects.filter(severity="ERROR")
        if request.user.role != Role.SUPER_ADMIN:
            qs = qs.filter(section__department=request.user.department)
        deleted, _ = qs.delete()
        return Response({"deleted": deleted})


class GlobalSearchView(APIView):
    """Section 59: search across faculty/subjects/classrooms/sections,
    respecting department scoping — a Dept Admin cannot search/see other
    departments' data."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        q = request.query_params.get("q", "").strip()
        if not q:
            return Response({"detail": "Provide a query string as ?q="}, status=400)

        user = request.user
        scoped = user.role != Role.SUPER_ADMIN

        faculty_qs = Faculty.objects.filter(Q(name__icontains=q) | Q(short_code__icontains=q) | Q(email__icontains=q))
        subject_qs = Subject.objects.filter(Q(name__icontains=q) | Q(code__icontains=q))
        classroom_qs = Classroom.objects.filter(Q(room_number__icontains=q) | Q(building__icontains=q))
        section_qs = Section.objects.filter(name__icontains=q)

        if scoped:
            faculty_qs = faculty_qs.filter(department=user.department)
            subject_qs = subject_qs.filter(department=user.department)
            classroom_qs = classroom_qs.filter(department=user.department)
            section_qs = section_qs.filter(department=user.department)

        return Response({
            "faculty": [{"id": f.id, "name": f.name, "short_code": f.short_code} for f in faculty_qs[:10]],
            "subjects": [{"id": s.id, "code": s.code, "name": s.name} for s in subject_qs[:10]],
            "classrooms": [{"id": c.id, "room_number": c.room_number, "type": c.room_type} for c in classroom_qs[:10]],
            "sections": [{"id": s.id, "name": str(s)} for s in section_qs[:10]],
        })