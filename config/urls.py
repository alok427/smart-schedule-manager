"""
Root URL configuration.

Each app's URLs are mounted under /api/<app>/ so the API surface mirrors
the app boundaries described in the architecture (Section 3). The admin
site is exposed unchanged at /admin/ for the Phase-1 admin dashboard.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from django.views.generic import RedirectView, TemplateView


def health_check(request):
    return JsonResponse({"status": "ok", "service": "smart-schedule-manager"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health_check, name="health_check"),
    path("api/accounts/", include("accounts.urls")),
    path("api/academics/", include("academics.urls")),
    path("api/", include("faculty.urls")),
    path("api/", include("classrooms.urls")),
    path("api/academic-calendar/", include("academic_calendar.urls")),
    path("api/scheduling/", include("scheduling.urls")),
    path("api/data-import/", include("data_import.urls")),
    path("api/data-export/", include("data_export.urls")),
    path("api/dashboard/", include("dashboard.urls")),
    path("api/notifications/", include("notifications.urls")),

    # Server-rendered pages (Section 46-48): Django templates + vanilla JS
    # calling the JSON API above. See static/js/api.js for the shared
    # fetch/auth helper every page uses.
    path("", RedirectView.as_view(url="/login/", permanent=False)),
    path("login/", TemplateView.as_view(template_name="login.html"), name="login_page"),
    path("dashboard/", TemplateView.as_view(template_name="dashboard.html"), name="dashboard_page"),
    path("manage-timetable/", TemplateView.as_view(template_name="manage_timetable.html"), name="manage_timetable_page"),
    path("faculty/", TemplateView.as_view(template_name="faculty_portal.html"), name="faculty_page"),
    path("student/", TemplateView.as_view(template_name="student_portal.html"), name="student_page"),
    path("notifications/", TemplateView.as_view(template_name="notifications.html"), name="notifications_page"),
    path("excel-import/", TemplateView.as_view(template_name="excel_import.html"), name="excel_import_page"),
    path("fixed-lectures/", TemplateView.as_view(template_name="fixed_lectures.html"), name="fixed_lectures_page"),
    path("faculty-admin/", TemplateView.as_view(template_name="faculty_admin.html"), name="faculty_admin_page"),
    path("subjects/", TemplateView.as_view(template_name="subjects.html"), name="subjects_page"),
    path("classrooms/", TemplateView.as_view(template_name="classrooms.html"), name="classrooms_page"),
    path("academic-calendar/", TemplateView.as_view(template_name="academic_calendar.html"), name="academic_calendar_page"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
