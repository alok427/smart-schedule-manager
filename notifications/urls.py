from django.urls import path

from . import views

urlpatterns = [
    path("mine/", views.MyNotificationsView.as_view(), name="my_notifications"),
    path("<int:pk>/read/", views.MarkNotificationReadView.as_view(), name="mark_notification_read"),
    path("mark-all-read/", views.MarkAllNotificationsReadView.as_view(), name="mark_all_notifications_read"),
]
