from django.contrib import admin

from .models import (
    AcademicYear,
    Batch,
    College,
    Department,
    Section,
    Semester,
    Subject,
    SubjectOffering,
    Year,
)


@admin.register(College)
class CollegeAdmin(admin.ModelAdmin):
    list_display = ("name", "code")
    search_fields = ("name", "code")


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ("label", "start_date", "end_date", "is_active")
    list_filter = ("is_active",)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "college", "is_active")
    list_filter = ("college", "is_active")
    search_fields = ("code", "name")


@admin.register(Year)
class YearAdmin(admin.ModelAdmin):
    list_display = ("department", "year_number", "is_active")
    list_filter = ("department", "is_active", "year_number")


@admin.register(Semester)
class SemesterAdmin(admin.ModelAdmin):
    list_display = ("year", "academic_year", "semester_number", "semester_type", "is_active")
    list_filter = ("semester_type", "academic_year", "is_active")


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ("department", "year", "name", "academic_year", "strength", "is_active")
    list_filter = ("department", "year", "academic_year", "is_active")
    search_fields = ("name",)


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ("section", "name", "strength")
    list_filter = ("section__department",)


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "department", "year", "category", "lecture_hours", "tutorial_hours",
                     "practical_hours", "credits", "is_active")
    list_filter = ("department", "year", "category", "is_active")
    search_fields = ("code", "name")


@admin.register(SubjectOffering)
class SubjectOfferingAdmin(admin.ModelAdmin):
    list_display = ("subject", "section", "semester", "faculty", "is_faculty_locked", "is_active")
    list_filter = ("semester", "section__department", "is_active")
    search_fields = ("subject__code", "subject__name")
