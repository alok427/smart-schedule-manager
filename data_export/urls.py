from django.urls import path

from . import views

urlpatterns = [
    path("excel/", views.ExportExcelView.as_view(), name="export_excel"),
    path("pdf/", views.ExportPDFView.as_view(), name="export_pdf"),
    path("ical/", views.ExportICalView.as_view(), name="export_ical"),
]
