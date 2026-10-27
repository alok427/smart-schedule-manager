from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from common.constants import GenerationStatus
from scheduling.models import TimetableVersion

from . import services


class _BaseExportView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    content_type = None
    filename_suffix = None

    def _get_current_version(self, request):
        section_id = request.query_params.get("section")
        semester_id = request.query_params.get("semester")
        if not section_id or not semester_id:
            return None, Response({"detail": "section and semester query params are required."}, status=400)

        version = TimetableVersion.objects.select_related(
            "section__department", "semester__academic_year"
        ).filter(section_id=section_id, semester_id=semester_id, status=GenerationStatus.CURRENT).first()
        if not version:
            return None, Response({"detail": "No published (Current) timetable exists for this selection."}, status=404)

        user = request.user
        if user.role in ("DEPT_ADMIN", "FACULTY", "STUDENT") and user.department_id != version.section.department_id:
            return None, Response({"detail": "Not authorized for this department."}, status=403)
        return version, None

    def _render(self, version):
        raise NotImplementedError

    def get(self, request):
        version, error = self._get_current_version(request)
        if error:
            return error
        buf = self._render(version)
        filename = f"{version.section}_{version.semester}_{self.filename_suffix}".replace(" ", "_")
        return FileResponse(buf, as_attachment=True, filename=filename, content_type=self.content_type)


class ExportExcelView(_BaseExportView):
    content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    filename_suffix = "timetable.xlsx"

    def _render(self, version):
        return services.export_excel(version, college_name=version.section.department.college.name)


class ExportPDFView(_BaseExportView):
    content_type = "application/pdf"
    filename_suffix = "timetable.pdf"

    def _render(self, version):
        return services.export_pdf(version, college_name=version.section.department.college.name)


class ExportICalView(_BaseExportView):
    content_type = "text/calendar"
    filename_suffix = "timetable.ics"

    def _render(self, version):
        return services.export_ical(version)
