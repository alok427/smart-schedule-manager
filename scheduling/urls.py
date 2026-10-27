from rest_framework.routers import DefaultRouter

from django.urls import path

from . import views

router = DefaultRouter()
router.register("fixed-lectures", views.FixedLectureViewSet, basename="fixed-lecture")

urlpatterns = [
    path("generate/", views.GenerateTimetableView.as_view(), name="generate_timetable"),
    path("generations/<int:pk>/", views.GenerationDetailView.as_view(), name="generation_detail"),
    path("timetable/", views.ViewTimetableView.as_view(), name="view_timetable"),
    path("history/", views.TimetableHistoryView.as_view(), name="timetable_history"),
    path("versions/<int:pk>/restore/", views.RestoreVersionView.as_view(), name="restore_version"),
    path("edit/move-session/", views.MoveSessionView.as_view(), name="move_session"),
    path("edit/change-classroom/", views.ChangeClassroomView.as_view(), name="change_classroom"),
    path("edit/change-faculty/", views.ChangeFacultyView.as_view(), name="change_faculty"),
] + router.urls
