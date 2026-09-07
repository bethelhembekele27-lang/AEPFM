from decimal import Decimal, InvalidOperation

from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.throttling import AnonRateThrottle
from rest_framework import status as http_status

from .models import Invoice, Payment
from .serializers import PublicInvoiceSerializer
from .audit import log_audit


class PublicReceiptUploadThrottle(AnonRateThrottle):
    """
    Separate scope from DRF's default anon throttle so this endpoint can be
    tuned independently — receipt uploads are rarer/heavier than invoice
    views and worth a tighter limit. Rate is set in settings.py under
    REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['public_receipt_upload'].
    """
    scope = 'public_receipt_upload'


class PublicInvoiceView(APIView):
    """
    GET /api/public/invoice/<token>/
    No login required — the UUID token in the URL IS the access control.
    Used by the SMS link a bidder receives when their invoice is generated.
    """
    permission_classes = [AllowAny]

    def get(self, request, token):
        invoice = get_object_or_404(
            Invoice.objects.select_related('winner').prefetch_related('lots'),
            publicToken=token,
        )
        return Response(PublicInvoiceSerializer(invoice).data)


class PublicReceiptUploadView(APIView):
    """
    POST /api/public/invoice/<token>/receipt/
    No login required. Bidder attaches a receipt file + payment details.
    Creates a Payment flagged submittedViaPublicLink=True, sitting in
    'pending_manager_review' — the Auction Manager reviews it for
    legitimacy (Phase 5) before Finance ever sees it as a normal payment.
    """
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]
    throttle_classes = [PublicReceiptUploadThrottle]

    def post(self, request, token):
        invoice = get_object_or_404(Invoice, publicToken=token)

        if invoice.status in ('paid', 'cancelled', 'waived'):
            return Response(
                {'error': 'This invoice is already closed and cannot accept a new receipt.'},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        receipt_file = request.FILES.get('receiptFile')
        amount_paid = request.data.get('amountPaid')
        payment_method = request.data.get('paymentMethod')
        payment_date = request.data.get('paymentDate')

        if not receipt_file:
            return Response({'receiptFile': ['This field is required.']}, status=http_status.HTTP_400_BAD_REQUEST)
        if not amount_paid:
            return Response({'amountPaid': ['This field is required.']}, status=http_status.HTTP_400_BAD_REQUEST)
        if not payment_method:
            return Response({'paymentMethod': ['This field is required.']}, status=http_status.HTTP_400_BAD_REQUEST)
        if not payment_date:
            return Response({'paymentDate': ['This field is required.']}, status=http_status.HTTP_400_BAD_REQUEST)

        try:
            amount_paid = Decimal(str(amount_paid))
        except InvalidOperation:
            return Response({'amountPaid': ['Must be a valid number.']}, status=http_status.HTTP_400_BAD_REQUEST)

        payment = Payment.objects.create(
            invoice=invoice,
            amountPaid=amount_paid,
            paymentMethod=payment_method,
            paymentDate=payment_date,
            receiptFile=receipt_file,
            submittedViaPublicLink=True,
            verificationStatus='pending_manager_review',
            paymentStatus='pending',
        )

        if invoice.status == 'pending_payment':
            previous = invoice.status
            invoice.status = 'payment_submitted'
            invoice.save(update_fields=['status', 'updatedAt'])
            log_audit(
                invoice, 'Receipt submitted via public link', request.user,
                previous, invoice.status,
                reason='Bidder self-submitted a payment receipt through the public invoice link.',
                action_type='upload_payment',
            )

        return Response(
            {
                'success': True,
                'message': 'Receipt received. It will be reviewed shortly.',
                'paymentId': payment.id,
            },
            status=http_status.HTTP_201_CREATED,
        )