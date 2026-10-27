import logging

from django.contrib.auth import get_user_model
from rest_framework import permissions, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .permissions import IsSuperAdminOrDeptAdmin
from .serializers import (
    ChangePasswordSerializer,
    SmartScheduleTokenObtainPairSerializer,
    UserCreateSerializer,
    UserSerializer,
)

User = get_user_model()
logger = logging.getLogger("accounts")


class LoginView(TokenObtainPairView):
    serializer_class = SmartScheduleTokenObtainPairSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            logger.info("Successful login for username=%s", request.data.get("username"))
        else:
            logger.warning("Failed login attempt for username=%s", request.data.get("username"))
        return response


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = request.user
        user.set_password(serializer.validated_data["new_password"])
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password"])
        logger.info("Password changed for user_id=%s", user.id)
        return Response({"detail": "Password updated successfully."})


class UserViewSet(viewsets.ModelViewSet):
    """
    User management, restricted to Super Admin / Department Admin.
    Department Admins are further restricted (in get_queryset) to users in
    their own department, and cannot create Super Admin accounts.
    """

    queryset = User.objects.all().select_related("department").order_by("username")
    permission_classes = [IsSuperAdminOrDeptAdmin]

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        return UserSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == "SUPER_ADMIN":
            return qs
        return qs.filter(department_id=user.department_id)

    def perform_create(self, serializer):
        requester = self.request.user
        role = serializer.validated_data.get("role")
        if requester.role == "DEPT_ADMIN":
            if role == "SUPER_ADMIN":
                raise PermissionDenied("Department Admins cannot create Super Admin accounts.")
            serializer.validated_data["department"] = requester.department
        serializer.save()
        logger.info("User created: %s by %s", serializer.instance.username, requester.username)
