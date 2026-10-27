from rest_framework import serializers

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


class CollegeSerializer(serializers.ModelSerializer):
    class Meta:
        model = College
        fields = ["id", "name", "code"]


class AcademicYearSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicYear
        fields = ["id", "label", "start_date", "end_date", "is_active"]


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "code", "name", "college", "is_active"]


class YearSerializer(serializers.ModelSerializer):
    class Meta:
        model = Year
        fields = ["id", "department", "year_number", "is_active"]


class SemesterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Semester
        fields = ["id", "year", "academic_year", "semester_number", "semester_type", "is_active"]


class SectionSerializer(serializers.ModelSerializer):
    department_code = serializers.CharField(source="department.code", read_only=True)
    year_number = serializers.IntegerField(source="year.year_number", read_only=True)

    class Meta:
        model = Section
        fields = ["id", "department", "department_code", "year", "year_number", "academic_year",
                  "name", "strength", "is_active"]


class BatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Batch
        fields = ["id", "section", "name", "strength"]


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ["id", "department", "year", "code", "name", "category", "lecture_hours",
                  "tutorial_hours", "practical_hours", "credits", "has_batches", "num_batches", "is_active"]

    def validate_practical_hours(self, value):
        if value % 2 != 0:
            raise serializers.ValidationError(
                "practical_hours must be even: practicals are scheduled as 2-period lab blocks."
            )
        return value


class SubjectOfferingSerializer(serializers.ModelSerializer):
    subject_code = serializers.CharField(source="subject.code", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    faculty_name = serializers.CharField(source="faculty.name", read_only=True, default=None)

    class Meta:
        model = SubjectOffering
        fields = ["id", "subject", "subject_code", "subject_name", "section", "semester",
                  "faculty", "faculty_name", "is_faculty_locked", "is_active"]
