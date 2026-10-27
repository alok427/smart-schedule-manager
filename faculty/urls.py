from rest_framework.routers import DefaultRouter

from django.urls import path

from . import views

router = DefaultRouter()
router.register("faculty", views.FacultyViewSet, basename="faculty")
router.register("faculty-assignment-rules", views.FacultyAssignmentRuleViewSet, basename="faculty-assignment-rule")

urlpatterns = [
    path("faculty/me/timetable/", views.MyFacultyTimetableView.as_view(), name="my_faculty_timetable"),
] + router.urls
