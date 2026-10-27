from rest_framework import serializers

from academics.models import Department, Section, Year
from .models import (
    FixedLecture,
    GenerationIssue,
    TimetableEntry,
    TimetableGeneration,
    TimetableVersion,
)


class GenerationCreateSerializer(serializers.Serializer):
    """Section 6/7/8: the generation scope controls."""

    academic_year = serializers.IntegerField()
    semester_type = serializers.ChoiceField(choices=["ODD", "EVEN"])
    scope_type = serializers.ChoiceField(choices=["COMPLETE", "SECTION", "DRAFT"])
    department_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    year_numbers = serializers.ListField(
        child=serializers.IntegerField(min_value=1, max_value=4), required=False, default=list,
        help_text="Which of Year 1-4 are ON for this run (Section 7). Empty = all active years.",
    )
    section_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)


class GenerationIssueSerializer(serializers.ModelSerializer):
    class Meta:
        model = GenerationIssue
        fields = ["id", "severity", "section", "subject", "message", "created_at"]


class TimetableGenerationSerializer(serializers.ModelSerializer):
    issues = GenerationIssueSerializer(many=True, read_only=True)
    section_names = serializers.SerializerMethodField()

    class Meta:
        model = TimetableGeneration
        fields = [
            "id", "academic_year", "semester_type", "scope_type", "status", "seed",
            "started_at", "completed_at", "failure_summary", "created_by", "created_at",
            "issues", "section_names",
        ]
        read_only_fields = fields

    def get_section_names(self, obj):
        return [str(s) for s in obj.sections.all()]


class TimetableEntryCellSerializer(serializers.ModelSerializer):
    """Section 12: the timetable cell — subject name/code, faculty, room.
    Deliberately excludes internal DB ids from the display payload."""

    subject_name = serializers.CharField(source="session.subject_offering.subject.name")
    subject_code = serializers.CharField(source="session.subject_offering.subject.code")
    session_type = serializers.CharField(source="session.session_type")
    faculty_name = serializers.SerializerMethodField()
    faculty_short_code = serializers.SerializerMethodField()
    classroom_number = serializers.SerializerMethodField()
    batch_name = serializers.SerializerMethodField()
    session_id = serializers.IntegerField(source="session.id")

    class Meta:
        model = TimetableEntry
        fields = [
            "day", "period_label", "start_time", "end_time", "is_fixed",
            "subject_name", "subject_code", "session_type",
            "faculty_name", "faculty_short_code", "classroom_number", "batch_name",
            "session_id",
        ]

    def get_faculty_name(self, obj):
        return obj.faculty.name if obj.faculty else None

    def get_faculty_short_code(self, obj):
        return obj.faculty.short_code if obj.faculty else None

    def get_classroom_number(self, obj):
        return obj.classroom.room_number if obj.classroom else None

    def get_batch_name(self, obj):
        return obj.batch.name if obj.batch else None


class TimetableVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimetableVersion
        fields = ["id", "section", "semester", "version_number", "status", "activated_at", "generation"]


class MoveSessionSerializer(serializers.Serializer):
    session_id = serializers.IntegerField()
    new_day = serializers.IntegerField(min_value=0, max_value=5)
    new_period_labels = serializers.ListField(child=serializers.CharField())


class ChangeClassroomSerializer(serializers.Serializer):
    session_id = serializers.IntegerField()
    new_classroom_id = serializers.IntegerField()


class ChangeFacultySerializer(serializers.Serializer):
    offering_id = serializers.IntegerField()
    new_faculty_id = serializers.IntegerField()


class FixedLectureSerializer(serializers.ModelSerializer):
    class Meta:
        model = FixedLecture
        fields = [
            "id", "academic_year", "subject_offering", "batch", "session_type",
            "faculty", "classroom", "day", "period_label", "is_active", "notes",
        ]
