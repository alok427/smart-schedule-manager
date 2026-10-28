from django.urls import path

from . import views

urlpatterns = [
    path("mine/", views.MyNotificationsView.as_view(), name="my_notifications"),
    path("<int:pk>/read/", views.MarkNotificationReadView.as_view(), name="mark_notification_read"),
    path("<int:pk>/delete/", views.DeleteNotificationView.as_view(), name="delete_notification"),
    path("mark-all-read/", views.MarkAllNotificationsReadView.as_view(), name="mark_all_notifications_read"),
    path("delete-read/", views.DeleteReadNotificationsView.as_view(), name="delete_read_notifications"),
    path("delete-all/", views.DeleteAllNotificationsView.as_view(), name="delete_all_notifications"),
]
