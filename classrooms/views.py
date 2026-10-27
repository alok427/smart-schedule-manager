from django.db.models import Q
from rest_framework import permissions, viewsets
from rest_framework.exceptions import ValidationError

from accounts.permissions import IsSuperAdminOrDeptAdmin
from common.constants import Role

from .models import Classroom
from .serializers import ClassroomSerializer


class ClassroomViewSet(viewsets.ModelViewSet):
    queryset = Classroom.objects.all()
    serializer_class = ClassroomSerializer
    filterset_fields = ["department", "room_type", "is_active"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.IsAuthenticated()]
        return [IsSuperAdminOrDeptAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_authenticated and user.role != Role.SUPER_ADMIN and user.department_id:
            qs = qs.filter(Q(department_id=user.department_id) | Q(department__isnull=True))
        return qs

    def _resolve_college(self, user, department):
        if department is not None:
            return department.college
        if user.department is not None:
            return user.department.college
        from academics.models import College
        college = College.objects.first()
        if college is None:
            raise ValidationError("No College exists yet — create one in /admin/ first.")
        return college

    def perform_create(self, serializer):
        user = self.request.user
        department = serializer.validated_data.get("department")
        if user.role == Role.DEPT_ADMIN:
            department = user.department
        college = self._resolve_college(user, department)
        serializer.save(department=department, college=college)

    def perform_update(self, serializer):
        user = self.request.user
        department = serializer.validated_data.get("department", serializer.instance.department)
        college = self._resolve_college(user, department)
        serializer.save(college=college)
