from django.urls import path
from .report_views import (
    ReportPreviewView, ReportGeneratePdfView, FilterOptionsView, RecentReportsView,
)

urlpatterns = [
    path('reports/preview/', ReportPreviewView.as_view(), name='report-preview'),
    path('reports/generate-pdf/', ReportGeneratePdfView.as_view(), name='report-generate-pdf'),
    path('reports/filter-options/', FilterOptionsView.as_view(), name='report-filter-options'),
    path('reports/recent/', RecentReportsView.as_view(), name='report-recent'),
]