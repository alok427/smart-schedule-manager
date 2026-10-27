from django.contrib import admin

from .models import AdditionalLoad, Activity, CoordinatorAssignment, FacultyActivity


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ("name", "department", "counts_toward_workload", "is_academic_timetable_activity",
                     "is_extra_activity")
    list_filter = ("department", "counts_toward_workload", "is_academic_timetable_activity")


@admin.register(FacultyActivity)
class FacultyActivityAdmin(admin.ModelAdmin):
    list_display = ("activity", "faculty", "section", "date", "day", "load_value_hours")
    list_filter = ("activity", "day")


@admin.register(CoordinatorAssignment)
class CoordinatorAssignmentAdmin(admin.ModelAdmin):
    list_display = ("faculty", "section", "academic_year", "load_value_hours", "is_active")
    list_filter = ("academic_year", "is_active")


@admin.register(AdditionalLoad)
class AdditionalLoadAdmin(admin.ModelAdmin):
    list_display = ("faculty", "semester", "description", "load_value_hours", "counts_toward_workload")
    list_filter = ("semester", "counts_toward_workload")
