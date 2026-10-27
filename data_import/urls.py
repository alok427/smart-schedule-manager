from django.urls import path

from . import views

urlpatterns = [
    path("template/", views.ImportTemplateDownloadView.as_view(), name="import_template_download"),
    path("import/", views.ImportExcelView.as_view(), name="import_excel"),
    path("batches/", views.ImportBatchListView.as_view(), name="import_batches"),
]
