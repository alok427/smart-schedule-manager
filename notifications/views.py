from django.utils import timezone
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification
from .serializers import NotificationSerializer


class MyNotificationsView(APIView):
    """Section 58: single in-app notification center. Everyone sees only
    their own notifications — there is no cross-user notification listing."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = Notification.objects.filter(recipient=request.user).order_by("-created_at")[:50]
        unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()
        return Response({"unread_count": unread_count, "notifications": NotificationSerializer(qs, many=True).data})


class MarkNotificationReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            notif = Notification.objects.get(pk=pk, recipient=request.user)
        except Notification.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)
        if not notif.is_read:
            notif.is_read = True
            notif.read_at = timezone.now()
            notif.save(update_fields=["is_read", "read_at"])
        return Response(NotificationSerializer(notif).data)


class MarkAllNotificationsReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        updated = Notification.objects.filter(recipient=request.user, is_read=False).update(
            is_read=True, read_at=timezone.now()
        )
        return Response({"marked_read": updated})


class DeleteNotificationView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        deleted, _ = Notification.objects.filter(pk=pk, recipient=request.user).delete()
        if not deleted:
            return Response({"detail": "Not found."}, status=404)
        return Response({"deleted": deleted})


class DeleteReadNotificationsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        deleted, _ = Notification.objects.filter(recipient=request.user, is_read=True).delete()
        return Response({"deleted": deleted})


class DeleteAllNotificationsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        deleted, _ = Notification.objects.filter(recipient=request.user).delete()
        return Response({"deleted": deleted})