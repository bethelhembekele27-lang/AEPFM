from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from invoices.cron_views import FlagOverdueView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('invoices.urls')),
    path('api/', include('invoices.report_urls')),
    path('api/', include('invoices.call_center_urls')),
    path('api/', include('invoices.employee_urls')),
    path('api/', include('invoices.public_urls')),
    path('api/', include('invoices.sms_urls')),
    path('api/cron/flag-overdue/', FlagOverdueView.as_view(), name='cron-flag-overdue'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)