from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("colleges", views.CollegeViewSet, basename="college")
router.register("academic-years", views.AcademicYearViewSet, basename="academic-year")
router.register("departments", views.DepartmentViewSet, basename="department")
router.register("years", views.YearViewSet, basename="year")
router.register("semesters", views.SemesterViewSet, basename="semester")
router.register("sections", views.SectionViewSet, basename="section")
router.register("subjects", views.SubjectViewSet, basename="subject")
router.register("subject-offerings", views.SubjectOfferingViewSet, basename="subject-offering")

urlpatterns = [
    path("student/me/timetable/", views.MyStudentTimetableView.as_view(), name="my_student_timetable"),
] + router.urls
