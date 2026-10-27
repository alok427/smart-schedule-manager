from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("calendars", views.AcademicCalendarViewSet, basename="academic-calendar")
router.register("working-days", views.WorkingDayViewSet, basename="working-day")
router.register("holidays", views.HolidayViewSet, basename="holiday")
router.register("special-working-days", views.SpecialWorkingDayViewSet, basename="special-working-day")
router.register("events", views.EventViewSet, basename="calendar-event")

urlpatterns = router.urls
