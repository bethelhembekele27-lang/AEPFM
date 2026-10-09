from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from invoices.views.cron import FlagOverdueView
from invoices.views.health import health_check

urlpatterns = [
    path('health/', health_check, name='health-check'),
    path(settings.DJANGO_ADMIN_URL, admin.site.urls),
    path('api/', include('invoices.urls.core')),
    path('api/', include('invoices.urls.reports')),
    path('api/', include('invoices.urls.call_center')),
    path('api/', include('invoices.urls.employees')),
    path('api/', include('invoices.urls.public')),
    path('api/', include('invoices.urls.sms')),
    path('api/cron/flag-overdue/', FlagOverdueView.as_view(), name='cron-flag-overdue'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)