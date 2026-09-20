from decimal import Decimal, InvalidOperation
from io import BytesIO

from django.shortcuts import get_object_or_404
from django.http import FileResponse
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.throttling import AnonRateThrottle
from rest_framework import status as http_status

from .models import Invoice, Payment
from .serializers import PublicInvoiceSerializer
from .audit import log_audit
from .pdf_rendering import load_invoice_images, render_invoice_html

IMAGE_NOT_CLEAR_MESSAGE = "ምስሉ ግልጽ አይደለም፣ እባክዎ ግልጽ ፎቶ አንስተው እንደገና ይስቀሉ"
FILE_NOT_VALID_MESSAGE = "ፋይሉ ትክክለኛ አይደለም፣ እባክዎ ትክክለኛ PDF ወይም ግልጽ ፎቶ ይስቀሉ"
FILE_TOO_LARGE_MESSAGE = "ፋይሉ በጣም ትልቅ ነው፣ እባክዎ ከ10MB ያነሰ ፋይል ይስቀሉ"
MIN_RECEIPT_FILE_SIZE = 20_000
MIN_PDF_SIZE = 5_000
MAX_RECEIPT_FILE_SIZE = 10 * 1024 * 1024
MIN_RECEIPT_DIMENSION = 300

ERROR_CODES = {
    IMAGE_NOT_CLEAR_MESSAGE: 'image_not_clear',
    FILE_NOT_VALID_MESSAGE: 'file_not_valid',
    FILE_TOO_LARGE_MESSAGE: 'file_too_large',
}


class PublicPdfThrottle(AnonRateThrottle):
    scope = 'public_invoice_pdf'


def _is_pdf(f):
    f.seek(0)
    head = f.read(5)
    f.seek(0)
    return head == b'%PDF-'


def _validate_pdf(f):
    if f.size < MIN_PDF_SIZE:
        return FILE_NOT_VALID_MESSAGE
    f.seek(max(f.size - 1024, 0))
    tail = f.read()
    f.seek(0)
    if b'%%EOF' not in tail:
        return FILE_NOT_VALID_MESSAGE
    return None


def _validate_receipt_file(receipt_file):
    """Accepts PDF or image, detected by content (not file extension)."""
    if receipt_file.size > MAX_RECEIPT_FILE_SIZE:
        return FILE_TOO_LARGE_MESSAGE
    if _is_pdf(receipt_file):
        return _validate_pdf(receipt_file)

    if receipt_file.size < MIN_RECEIPT_FILE_SIZE:
        return IMAGE_NOT_CLEAR_MESSAGE
    try:
        from PIL import Image
        receipt_file.seek(0)
        img = Image.open(receipt_file)
        img.verify()
        receipt_file.seek(0)
        img = Image.open(receipt_file)
        width, height = img.size
        if width < MIN_RECEIPT_DIMENSION or height < MIN_RECEIPT_DIMENSION:
            return IMAGE_NOT_CLEAR_MESSAGE
    except Exception:
        return FILE_NOT_VALID_MESSAGE
    finally:
        receipt_file.seek(0)
    return None


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


@method_decorator(xframe_options_exempt, name='get')
class PublicInvoicePdfView(APIView):
    """
    GET /api/public/invoice/<token>/pdf/
    No login required. Renders the SAME invoice-letter template used by
    the authenticated "Generate invoice PDF" button (via pdf_rendering.py)
    so bidders always see exactly what staff see — no separate template
    to drift out of sync. Generated fresh on every request; nothing is
    saved to disk, so this always reflects the invoice's current state
    (fee %, due date, etc.) even if it was edited after the SMS was sent.
    """
    permission_classes = [AllowAny]
    throttle_classes = [PublicPdfThrottle]

    def get(self, request, token):
        from weasyprint import HTML

        invoice = get_object_or_404(
            Invoice.objects.select_related('winner').prefetch_related('lots'),
            publicToken=token,
        )

        images = load_invoice_images()
        try:
            data = invoice.letterData or {}
            html_string = render_invoice_html(
                invoice, data.get('auctionRefNumber', ''), images,
                data.get('amountInWords', ''), data.get('feeInWords', ''), data.get('officeAddress', ''),
                data.get('totalAmount') or None, data.get('feeAmount') or None, data.get('bankAccount', ''),
                data.get('paragraph1', ''), data.get('paragraph2', ''),
            )
            pdf_bytes = HTML(string=html_string).write_pdf()
        except Exception as e:
            return Response(
                {'error': f'PDF generation failed: {str(e)}'},
                status=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return FileResponse(
            BytesIO(pdf_bytes),
            as_attachment=False,  # display inline in the browser tab, not a forced download
            filename=f"Invoice_{invoice.invoiceNumber}.pdf",
            content_type='application/pdf',
        )


class PublicReceiptUploadView(APIView):
    """
    POST /api/public/invoice/<token>/receipt/
    No login required. Bidder attaches only a receipt image — no amount,
    method, or date fields are collected from them anymore. Those are
    defaulted server-side. Creates a Payment flagged
    submittedViaPublicLink=True, sitting in 'pending_manager_review' —
    the Auction Manager reviews it for legitimacy (Phase 5) before
    Finance ever sees it as a normal payment.
    """
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]
    throttle_classes = [PublicReceiptUploadThrottle]

    def post(self, request, token):
        invoice = get_object_or_404(Invoice, publicToken=token)

        if invoice.status in ('paid', 'cancelled', 'waived'):
            return Response(
                {'error': 'This invoice is already closed and cannot accept a new receipt.', 'code': 'invoice_closed'},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        receipt_file = request.FILES.get('receiptFile')
        if not receipt_file:
            return Response(
                {'error': 'This field is required.', 'code': 'file_required'},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        image_error = _validate_receipt_file(receipt_file)
        if image_error:
            return Response(
                {'error': image_error, 'code': ERROR_CODES.get(image_error, 'file_not_valid')},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        # amountPaid / paymentMethod / paymentDate are no longer collected
        # from the bidder — defaulted here instead.
        amount_paid = request.data.get('amountPaid') or invoice.totalAmount
        payment_method = request.data.get('paymentMethod') or 'unspecified'
        payment_date = request.data.get('paymentDate') or timezone.localdate()

        try:
            amount_paid = Decimal(str(amount_paid))
        except InvalidOperation:
            amount_paid = invoice.totalAmount

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