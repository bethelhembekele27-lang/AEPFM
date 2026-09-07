from django.urls import path
from .public_views import PublicInvoiceView, PublicReceiptUploadView

urlpatterns = [
    path('public/invoice/<uuid:token>/', PublicInvoiceView.as_view(), name='public-invoice-detail'),
    path('public/invoice/<uuid:token>/receipt/', PublicReceiptUploadView.as_view(), name='public-invoice-receipt-upload'),
]