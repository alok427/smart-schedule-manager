from rest_framework import serializers

from .models import Classroom


class ClassroomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Classroom
        fields = ["id", "college", "department", "room_number", "building", "room_type", "capacity", "is_active"]
        read_only_fields = ["college"]
