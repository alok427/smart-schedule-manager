from rest_framework import serializers

from .models import Faculty, FacultyAssignmentRule, FacultyLoad


class FacultySerializer(serializers.ModelSerializer):
    class Meta:
        model = Faculty
        fields = ["id", "department", "name", "email", "short_code", "designation",
                  "faculty_type", "max_lectures_per_day", "max_lectures_per_week", "is_active"]


class FacultyLoadSerializer(serializers.ModelSerializer):
    class Meta:
        model = FacultyLoad
        fields = ["id", "faculty", "generation", "semester", "lecture_count",
                  "tutorial_count", "practical_periods", "additional_load_hours"]


class FacultyAssignmentRuleSerializer(serializers.ModelSerializer):
    faculty_name = serializers.CharField(source="faculty.name", read_only=True)
    subject_code = serializers.CharField(source="subject.code", read_only=True, default=None)

    class Meta:
        model = FacultyAssignmentRule
        fields = [
            "id", "faculty", "faculty_name", "department", "subject", "subject_code",
            "subject_category", "allowed_years", "allowed_semesters", "allowed_sections",
            "max_lectures", "specific_lecture_count",
            "preferred_day", "preferred_slot_label", "fixed_day", "fixed_slot_label",
            "is_generator_eligible", "is_active",
        ]

    def validate(self, data):
        department = data.get("department") or getattr(self.instance, "department", None)
        subject = data.get("subject") or getattr(self.instance, "subject", None)
        subject_category = data.get("subject_category") or getattr(self.instance, "subject_category", None)
        if not any([department, subject, subject_category]):
            raise serializers.ValidationError(
                "An assignment rule must scope to at least a department, subject, or subject category."
            )
        return data
