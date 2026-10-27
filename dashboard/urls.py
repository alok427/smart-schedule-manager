from django.urls import path

from . import views

urlpatterns = [
    path("stats/", views.DashboardStatsView.as_view(), name="dashboard_stats"),
    path("search/", views.GlobalSearchView.as_view(), name="global_search"),
]
