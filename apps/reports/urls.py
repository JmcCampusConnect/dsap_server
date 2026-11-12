from django.urls import path

from apps.reports.views import (
    ExportReportView,
    ReportOptionsView,
    ReportSummaryView,
    RequestReportListView,
    RevenueReportView,
)

urlpatterns = [
    path("summary/", ReportSummaryView.as_view(), name="report-summary"),
    path("requests/", RequestReportListView.as_view(), name="report-requests"),
    path("revenue/", RevenueReportView.as_view(), name="report-revenue"),
    path("export/", ExportReportView.as_view(), name="report-export"),
    path("options/", ReportOptionsView.as_view(), name="report-options"),
]
