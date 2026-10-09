from django.conf import settings
from django.utils import timezone
import hmac
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status as http_status
from invoices.models import Invoice, AuditLog


class FlagOverdueView(APIView):
    """POST /api/cron/flag-overdue/ — protected by a shared secret header
    (X-Cron-Secret), not session auth, since an external pinger has no login."""
    permission_classes = [AllowAny]

    def post(self, request):
        secret = request.headers.get('X-Cron-Secret', '')
        if not settings.CRON_SECRET or not hmac.compare_digest(secret.encode(), settings.CRON_SECRET.encode()):
            return Response({'error': 'Forbidden'}, status=http_status.HTTP_403_FORBIDDEN)

        today = timezone.localdate()
        overdue = Invoice.objects.filter(status='pending_payment', dueDate__lt=today, smsSentAt__isnull=False)
        count = 0
        for invoice in overdue:
            previous_status = invoice.status
            invoice.status = 'overdue'
            invoice.save(update_fields=['status', 'updatedAt'])
            AuditLog.objects.create(invoice=invoice, action='Mark overdue', performedBy=None, userRole='',
                                     previousValue=previous_status, newValue='overdue',
                                     reason='Due date passed with no payment (automated)')
            count += 1
        return Response({'flagged': count})
