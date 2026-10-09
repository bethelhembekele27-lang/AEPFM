from django.urls import path
from invoices.views.call_center import CallCenterListView, CallCenterNoteView

urlpatterns = [
    path('call-center/', CallCenterListView.as_view(), name='call-center-list'),
    path('call-center/<int:invoice_id>/note/', CallCenterNoteView.as_view(), name='call-center-note'),
]