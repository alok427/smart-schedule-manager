import logging
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from rest_framework import permissions
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from academics.models import Department, Year
from accounts.permissions import IsSuperAdminOrDeptAdmin

from .models import ImportBatch
from .serializers import ImportBatchSerializer
from .services import run_import

logger = logging.getLogger("data_import")


class ImportTemplateDownloadView(APIView):
    """Section 55: 'Download Excel Template' button target. Generates the
    template on first request if it doesn't exist yet, then serves it."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Built in memory on every request: no files are read or written, so it
        # works on Vercel (read-only filesystem, /media is not deployed).
        from io import BytesIO

        from django.http import HttpResponse

        from .management.commands.create_excel_template import build_workbook

        buffer = BytesIO()
        build_workbook().save(buffer)
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="college_timetable_excel_template.xlsx"'
        return response


class ImportExcelView(APIView):
    """Section 50/54: upload + import. Requires department_id; year_id is
    needed if the Subject sheet will be used."""

    permission_classes = [IsSuperAdminOrDeptAdmin]
    parser_classes = [MultiPartParser]

    def post(self, request):
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return Response({"detail": "No file uploaded. Send it as multipart field 'file'."}, status=400)

        department_id = request.data.get("department_id")
        if not department_id:
            return Response({"detail": "department_id is required."}, status=400)
        department = get_object_or_404(Department, pk=department_id)

        if request.user.role == "DEPT_ADMIN" and request.user.department_id != department.id:
            return Response({"detail": "Not authorized for this department."}, status=403)

        year = None
        year_id = request.data.get("year_id")
        if year_id:
            year = get_object_or_404(Year, pk=year_id, department=department)

        batch = run_import(uploaded_file, department=department, year=year, uploaded_by=request.user)
        logger.info(
            "Import '%s' by %s: status=%s faculty=%d subjects=%d classrooms=%d warnings=%d errors=%d",
            batch.original_filename, request.user.username, batch.status,
            batch.faculty_imported, batch.subjects_imported, batch.classrooms_imported,
            batch.warning_count, batch.error_count,
        )
        out = ImportBatchSerializer(batch).data
        return Response(out, status=201 if batch.status != "FAILED" else 400)


class ImportBatchListView(APIView):
    permission_classes = [IsSuperAdminOrDeptAdmin]

    def get(self, request):
        qs = ImportBatch.objects.all().order_by("-created_at")
        if request.user.role == "DEPT_ADMIN":
            qs = qs.filter(department=request.user.department)
        return Response(ImportBatchSerializer(qs[:50], many=True).data)
