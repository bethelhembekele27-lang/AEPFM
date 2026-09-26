from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status as http_status

from .models import Invoice
from .permissions import has_permission
from .audit import log_audit

UNPAID_STATUSES = ['invoice_generated', 'pending_payment', 'payment_submitted', 'under_verification', 'overdue']

STATUS_FILTER_CHOICES = [
    {'value': '', 'label': 'All unpaid statuses'},
    {'value': 'invoice_generated', 'label': 'Invoice Generated'},
    {'value': 'pending_payment', 'label': 'Pending Payment'},
    {'value': 'payment_submitted', 'label': 'Payment Submitted'},
    {'value': 'under_verification', 'label': 'Under Verification'},
    {'value': 'overdue', 'label': 'Overdue'},
]


class CallCenterListView(APIView):
    """
    GET /api/call-center/ — unpaid invoices sorted by due date ascending.
    Readable by any authenticated role (viewer included) — write access to
    notes is gated separately in CallCenterNoteView.
    Optional ?status=overdue to narrow to one status.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        status_filter = request.query_params.get('status')
        qs = Invoice.objects.filter(status__in=UNPAID_STATUSES).select_related('winner', 'winner__auction')
        if status_filter:
            if status_filter not in UNPAID_STATUSES:
                return Response({'error': f'Invalid status: {status_filter}'}, status=http_status.HTTP_400_BAD_REQUEST)
            qs = qs.filter(status=status_filter)
        qs = qs.order_by('dueDate')

        rows = []
        for inv in qs:
            lot_names = list(inv.lots.values_list('auctionName', flat=True))
            if lot_names:
                auction_label = lot_names[0]
                if len(lot_names) > 1:
                    auction_label += f" +{len(lot_names) - 1} more"
            else:
                auction_label = '—'

            rows.append({
                'id': inv.id,
                'bidderName': inv.winner.bidderName,
                'phone': inv.winner.winnerPhone,
                'companyName': inv.winner.companyName or '—',
                'auction': auction_label,
                'amountDue': str(inv.totalAmount),
                'dueDate': str(inv.dueDate),
                'status': inv.status,
                'callNotes': inv.callNotes,
            })

        return Response({
            'count': len(rows),
            'statusFilters': STATUS_FILTER_CHOICES,
            'rows': rows,
        })


class CallCenterNoteView(APIView):
    """
    POST /api/call-center/<invoice_id>/note/ — update callNotes.
    Restricted to administrator + call_operator via manage_call_center.
    Everyone else can read notes through CallCenterListView above, but
    cannot write here.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, invoice_id):
        if not has_permission(request.user, 'manage_call_center'):
            return Response(
                {'error': 'Only CRM / Call Center Officers can add notes here.'},
                status=http_status.HTTP_403_FORBIDDEN,
            )

        try:
            invoice = Invoice.objects.get(id=invoice_id)
        except Invoice.DoesNotExist:
            return Response({'error': 'Invoice not found'}, status=http_status.HTTP_404_NOT_FOUND)

        previous_note = invoice.callNotes
        note = request.data.get('callNotes', '')
        invoice.callNotes = note
        invoice.save(update_fields=['callNotes', 'updatedAt'])

        log_audit(
            invoice, 'Call center note updated', request.user,
            previous_value=previous_note[:100], new_value=note[:100],
            action_type='add_call_note',
        )

        return Response({'id': invoice.id, 'callNotes': invoice.callNotes})