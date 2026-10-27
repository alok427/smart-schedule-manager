from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()


class SmartScheduleTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Adds role/department claims to the JWT so the frontend can route
    users to the correct portal without an extra round trip."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["department_id"] = user.department_id
        token["full_name"] = user.get_full_name() or user.username
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["role"] = self.user.role
        data["department_id"] = self.user.department_id
        data["must_change_password"] = self.user.must_change_password
        return data


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id", "username", "first_name", "last_name", "email",
            "role", "department", "section", "phone_number", "is_active",
            "must_change_password", "date_joined",
        ]
        read_only_fields = ["id", "date_joined"]


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = [
            "id", "username", "first_name", "last_name", "email",
            "role", "department", "section", "phone_number", "password",
        ]

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.must_change_password = True
        user.save()
        return user


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value
