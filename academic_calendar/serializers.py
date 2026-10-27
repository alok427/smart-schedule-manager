from rest_framework import serializers

from .models import AcademicCalendar, Event, Holiday, SpecialWorkingDay, WorkingDay


class AcademicCalendarSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicCalendar
        fields = ["id", "academic_year", "department", "semester_start", "semester_end"]


class WorkingDaySerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkingDay
        fields = ["id", "calendar", "day", "is_working"]


class HolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Holiday
        fields = ["id", "calendar", "date", "name"]


class SpecialWorkingDaySerializer(serializers.ModelSerializer):
    class Meta:
        model = SpecialWorkingDay
        fields = ["id", "calendar", "date", "name", "follows_day_schedule"]


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = ["id", "calendar", "name", "description", "start_date", "end_date", "affects_timetable"]
