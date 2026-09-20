from django.core.management.base import BaseCommand
from django.utils import timezone

from invoices.models import Invoice, AuditLog


class Command(BaseCommand):
    """
    Run daily: python manage.py flag_overdue_invoices
    Moves any 'pending_payment' invoice past its dueDate to 'overdue',
    matching the transition rules (pending_payment -> overdue is allowed).
    Same logic Celery would have run — this just needs something external
    to trigger it on a schedule instead of Celery Beat.
    """
    help = "Marks pending_payment invoices as overdue once their dueDate has passed."

    def handle(self, *args, **options):
        today = timezone.localdate()
        overdue = Invoice.objects.filter(status='pending_payment', dueDate__lt=today, smsSentAt__isnull=False)

        count = 0
        for invoice in overdue:
            previous_status = invoice.status
            invoice.status = 'overdue'
            invoice.save(update_fields=['status', 'updatedAt'])
            AuditLog.objects.create(
                invoice=invoice,
                action='Mark overdue',
                performedBy=None,          # no human involved — system action
                userRole='',
                previousValue=previous_status,
                newValue='overdue',
                reason='Due date passed with no payment (automated)',
            )
            count += 1

        self.stdout.write(self.style.SUCCESS(f"Flagged {count} invoice(s) as overdue."))