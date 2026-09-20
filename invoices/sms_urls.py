from django.urls import path
from .sms_views import SmsPreviewView, SmsSendView

urlpatterns = [
    path('invoices/<int:invoice_id>/sms/preview/', SmsPreviewView.as_view(), name='sms-preview'),
    path('invoices/<int:invoice_id>/sms/send/', SmsSendView.as_view(), name='sms-send'),
]
