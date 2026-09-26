from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    AuctionViewSet, WinnerViewSet, InvoiceViewSet,
    AttachmentDeleteView, PaymentDeleteView, AuditLogListView, AuditLogClearView, AuditLogFilterOptionsView, FeeConfigView, LoginView,
    OfficeSettingsView, ManualWinnerCreateView, GoogleLoginView,
)
from .manager_review_views import PendingReceiptsView, ReceiptReviewView, ReceiptExtractView, VerifyEtCheckView

from .import_views import (
    ImportBatchViewSet, ImportBatchPreviewView, ImportBatchConfirmView,
)

router = DefaultRouter()
router.register(r'auctions', AuctionViewSet, basename='auction')
router.register(r'winners', WinnerViewSet, basename='winner')
router.register(r'invoices', InvoiceViewSet, basename='invoice')
router.register(r'import-batches', ImportBatchViewSet, basename='import-batch')

urlpatterns = [
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/google/', GoogleLoginView.as_view(), name='login-google'),
    path('import-batches/preview/', ImportBatchPreviewView.as_view(), name='import-batch-preview'),
    path('import-batches/confirm/', ImportBatchConfirmView.as_view(), name='import-batch-confirm'),

    path('attachments/<int:pk>/', AttachmentDeleteView.as_view(), name='attachment-delete'),
    path('payments/<int:pk>/', PaymentDeleteView.as_view(), name='payment-delete'),
    path('audit-logs/', AuditLogListView.as_view(), name='audit-log-list'),
    path('audit-logs/filter-options/', AuditLogFilterOptionsView.as_view(), name='audit-log-filter-options'),
    path('fee-config/', FeeConfigView.as_view(), name='fee-config'),
    path('office-settings/', OfficeSettingsView.as_view(), name='office-settings'),
    path('winners/manual/', ManualWinnerCreateView.as_view(), name='winner-manual-create'),
    path('audit-logs/filter-options/', AuditLogFilterOptionsView.as_view(), name='audit-log-filter-options'),
    path('audit-logs/clear/', AuditLogClearView.as_view(), name='audit-log-clear'),  # <-- add

    path('receipts/', PendingReceiptsView.as_view(), name='receipts-pending'),
    path('receipts/<int:payment_id>/review/', ReceiptReviewView.as_view(), name='receipt-review'),
    path('receipts/<int:payment_id>/extract/', ReceiptExtractView.as_view(), name='receipt-extract'),
    path('receipts/<int:payment_id>/verify-transaction/', VerifyEtCheckView.as_view(), name='receipt-verify-transaction'),

    path('', include(router.urls)),
]