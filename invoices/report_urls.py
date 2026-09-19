from django.urls import path
from .public_views import PublicInvoiceView, PublicInvoicePdfView, PublicReceiptUploadView

urlpatterns = [
    path('public/invoice/<uuid:token>/', PublicInvoiceView.as_view(), name='public-invoice-detail'),
    path('public/invoice/<uuid:token>/pdf/', PublicInvoicePdfView.as_view(), name='public-invoice-pdf'),
    path('public/invoice/<uuid:token>/receipt/', PublicReceiptUploadView.as_view(), name='public-invoice-receipt-upload'),
]