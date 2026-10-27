from django.contrib import admin

from .models import (
    Faculty,
    FacultyAssignmentRule,
    FacultyAvailability,
    FacultyLoad,
    FacultyPreference,
    FacultyProfile,
    FacultySubjectPreference,
)


@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    list_display = ("short_code", "name", "department", "faculty_type", "designation",
                     "max_lectures_per_day", "max_lectures_per_week", "is_active")
    list_filter = ("department", "faculty_type", "is_active")
    search_fields = ("name", "short_code", "email")


@admin.register(FacultyProfile)
class FacultyProfileAdmin(admin.ModelAdmin):
    list_display = ("faculty", "office_location", "joining_date")


@admin.register(FacultyAvailability)
class FacultyAvailabilityAdmin(admin.ModelAdmin):
    list_display = ("faculty", "day", "start_time", "end_time", "reason")
    list_filter = ("day", "faculty__department")


@admin.register(FacultyPreference)
class FacultyPreferenceAdmin(admin.ModelAdmin):
    list_display = ("faculty", "prefers_morning", "prefers_no_back_to_back", "max_consecutive_lectures")


@admin.register(FacultySubjectPreference)
class FacultySubjectPreferenceAdmin(admin.ModelAdmin):
    list_display = ("faculty", "subject", "priority", "is_eligible")
    list_filter = ("is_eligible",)
    search_fields = ("faculty__name", "subject__code")


@admin.register(FacultyAssignmentRule)
class FacultyAssignmentRuleAdmin(admin.ModelAdmin):
    list_display = ("faculty", "department", "subject", "subject_category",
                     "is_generator_eligible", "is_active")
    list_filter = ("subject_category", "is_generator_eligible", "is_active")


@admin.register(FacultyLoad)
class FacultyLoadAdmin(admin.ModelAdmin):
    list_display = ("faculty", "generation", "semester", "lecture_count", "tutorial_count",
                     "practical_periods", "additional_load_hours")
    list_filter = ("semester",)
