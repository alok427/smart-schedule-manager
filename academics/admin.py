from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ActionForm

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


class OfferingActionForm(ActionForm):
    """Adds a Semester picker next to the admin action dropdown."""

    semester = forms.ModelChoiceField(
        queryset=Semester.objects.select_related("year", "academic_year"),
        required=False,
        label="Semester",
    )


@admin.action(description="Create offerings: link selected subjects to ALL sections of their year (choose a Semester first)")
def create_offerings_for_all_sections(modeladmin, request, queryset):
    """Excel import creates Subjects but not SubjectOfferings, and the generator
    schedules offerings only. This links each selected subject to every active
    section of the same year, for the chosen semester. Safe to run twice."""
    semester_id = request.POST.get("semester")
    if not semester_id:
        modeladmin.message_user(
            request, "First pick a Semester in the box next to the action dropdown, then click Go.", messages.ERROR
        )
        return
    semester = Semester.objects.select_related("year", "academic_year").get(pk=semester_id)

    created = existing = wrong_year = 0
    for subject in queryset:
        if subject.year_id != semester.year_id:
            wrong_year += 1
            continue
        sections = Section.objects.filter(
            year=subject.year, academic_year=semester.academic_year, is_active=True
        )
        for section in sections:
            _, was_created = SubjectOffering.objects.get_or_create(
                subject=subject, section=section, semester=semester
            )
            if was_created:
                created += 1
            else:
                existing += 1

    modeladmin.message_user(
        request,
        f"Created {created} offering(s); {existing} already existed.",
        messages.SUCCESS if created else messages.WARNING,
    )
    if wrong_year:
        modeladmin.message_user(
            request,
            f"{wrong_year} subject(s) skipped: their Year does not match the chosen Semester's Year.",
            messages.WARNING,
        )


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    action_form = OfferingActionForm
    actions = [create_offerings_for_all_sections]
    list_display = ("code", "name", "department", "year", "category", "lecture_hours", "tutorial_hours",
                     "practical_hours", "credits", "is_active")
    list_filter = ("department", "year", "category", "is_active")
    search_fields = ("code", "name")


@admin.register(SubjectOffering)
class SubjectOfferingAdmin(admin.ModelAdmin):
    list_display = ("subject", "section", "semester", "faculty", "is_faculty_locked", "is_active")
    list_filter = ("semester", "section__department", "is_active")
    search_fields = ("subject__code", "subject__name")
