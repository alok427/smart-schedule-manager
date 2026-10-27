from django.contrib import admin

from .models import AcademicCalendar, Event, Holiday, SpecialWorkingDay, WorkingDay


@admin.register(AcademicCalendar)
class AcademicCalendarAdmin(admin.ModelAdmin):
    list_display = ("academic_year", "department", "semester_start", "semester_end")
    list_filter = ("academic_year", "department")


@admin.register(WorkingDay)
class WorkingDayAdmin(admin.ModelAdmin):
    list_display = ("calendar", "day", "is_working")
    list_filter = ("day", "is_working")


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ("name", "date", "calendar")
    date_hierarchy = "date"


@admin.register(SpecialWorkingDay)
class SpecialWorkingDayAdmin(admin.ModelAdmin):
    list_display = ("date", "name", "follows_day_schedule", "calendar")
    date_hierarchy = "date"


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("name", "start_date", "end_date", "affects_timetable", "calendar")
    list_filter = ("affects_timetable",)
    date_hierarchy = "start_date"
