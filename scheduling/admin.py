from django.contrib import admin

from .models import (
    FixedLecture,
    GenerationIssue,
    TimetableChange,
    TimetableEntry,
    TimetableGeneration,
    TimetableSession,
    TimetableVersion,
)


class GenerationIssueInline(admin.TabularInline):
    model = GenerationIssue
    extra = 0
    readonly_fields = ("severity", "section", "subject", "message", "created_at")
    can_delete = False


@admin.register(TimetableGeneration)
class TimetableGenerationAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "scope_type", "academic_year", "semester_type",
                     "created_by", "created_at", "completed_at")
    list_filter = ("status", "scope_type", "academic_year", "semester_type")
    filter_horizontal = ("departments", "years", "sections")
    inlines = [GenerationIssueInline]
    readonly_fields = ("created_at", "updated_at")


@admin.register(GenerationIssue)
class GenerationIssueAdmin(admin.ModelAdmin):
    list_display = ("generation", "severity", "section", "subject", "message")
    list_filter = ("severity",)


@admin.register(FixedLecture)
class FixedLectureAdmin(admin.ModelAdmin):
    list_display = ("subject_offering", "faculty", "classroom", "day", "period_label",
                     "session_type", "is_active")
    list_filter = ("day", "session_type", "is_active")


@admin.register(TimetableSession)
class TimetableSessionAdmin(admin.ModelAdmin):
    list_display = ("subject_offering", "session_type", "sequence_number", "duration_periods",
                     "batch", "is_scheduled")
    list_filter = ("session_type", "is_scheduled")


@admin.register(TimetableEntry)
class TimetableEntryAdmin(admin.ModelAdmin):
    list_display = ("generation", "section", "day", "period_label", "faculty", "classroom", "is_fixed")
    list_filter = ("generation", "day", "is_fixed")
    search_fields = ("section__name", "faculty__short_code", "classroom__room_number")


@admin.register(TimetableVersion)
class TimetableVersionAdmin(admin.ModelAdmin):
    list_display = ("section", "semester", "version_number", "status", "generation", "activated_at")
    list_filter = ("status", "semester")


@admin.register(TimetableChange)
class TimetableChangeAdmin(admin.ModelAdmin):
    list_display = ("source", "description", "changed_by", "created_at")
    list_filter = ("source",)
    readonly_fields = ("created_at",)
