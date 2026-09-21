from django.db import transaction
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status as http_status

from .models import Payment
from .permissions import has_permission
from .audit import log_audit
from .sms import send_sms, normalize_phone


class PendingReceiptsView(APIView):
    """
    GET /api/receipts/
    Returns all payments currently awaiting manager review (or any
    verificationStatus passed as ?verificationStatus=... for filtering
    history rows too).
    Only accessible to users with manager_verify_receipt privilege.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not has_permission(request.user, 'manager_verify_receipt'):
            return Response({'error': 'Permission denied'}, status=http_status.HTTP_403_FORBIDDEN)

        status_filter = request.query_params.get('verificationStatus', 'pending_manager_review')

        qs = (
            Payment.objects
            .filter(verificationStatus=status_filter, submittedViaPublicLink=True)
            .select_related('invoice', 'invoice__winner')
            .order_by('-uploadedAt')
        )

        # Import here to avoid a circular-import at module level
        from .serializers import ManagerPaymentSerializer
        return Response(ManagerPaymentSerializer(qs, many=True, context={'request': request}).data)


class ReceiptReviewView(APIView):
    """
    POST /api/receipts/<payment_id>/review/
    Body: { "decision": "approve" | "reject", "note": "<string>" }

    approve → verificationStatus=manager_approved, invoice→under_verification
    reject  → verificationStatus=manager_rejected, invoice→pending_payment + SMS to bidder
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, payment_id):
        if not has_permission(request.user, 'manager_verify_receipt'):
            return Response({'error': 'Permission denied'}, status=http_status.HTTP_403_FORBIDDEN)

        try:
            payment = (
                Payment.objects
                .select_related('invoice', 'invoice__winner')
                .get(pk=payment_id)
            )
        except Payment.DoesNotExist:
            return Response({'error': 'Payment not found'}, status=http_status.HTTP_404_NOT_FOUND)

        if payment.verificationStatus != 'pending_manager_review':
            return Response(
                {'error': 'This receipt has already been reviewed.'},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        decision = request.data.get('decision')
        note = request.data.get('note', '').strip()

        if decision not in ('approve', 'reject'):
            return Response(
                {'error': "decision must be 'approve' or 'reject'"},
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        if decision == 'reject' and not note:
            return Response(
                {'error': 'A note is required when rejecting a receipt.'},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        invoice = payment.invoice
        previous_status = invoice.status

        with transaction.atomic():
            payment.managerVerifiedBy = request.user
            payment.managerVerifiedDate = timezone.now()
            payment.managerNote = note

            if decision == 'approve':
                payment.verificationStatus = 'manager_approved'
                invoice.status = 'under_verification'
                log_audit(
                    invoice,
                    'Receipt approved by manager',
                    request.user,
                    previous_status,
                    invoice.status,
                    reason=note,
                    action_type='other',
                )
            else:
                payment.verificationStatus = 'manager_rejected'
                invoice.status = 'pending_payment'
                log_audit(
                    invoice,
                    'Receipt rejected by manager',
                    request.user,
                    previous_status,
                    invoice.status,
                    reason=note,
                    action_type='other',
                )

            payment.save(update_fields=[
                'verificationStatus', 'managerVerifiedBy',
                'managerVerifiedDate', 'managerNote',
            ])
            invoice.save(update_fields=['status', 'updatedAt'])

        # Send SMS on rejection so the bidder knows to resubmit
        if decision == 'reject':
            winner = invoice.winner
            phone = normalize_phone(winner.winnerPhone)
            if phone:
                name = winner.bidderNameAmharic or winner.bidderName
                # Build absolute base URL without a trailing slash
                base_url = request.build_absolute_uri('/').rstrip('/')
                public_url = f"{base_url}/invoice/{invoice.publicToken}"
                message = (
                    f"ውድ {name}፣ "
                    f"የላኩት የክፍያ ደረሰኝ ውድቅ ተደርጓል። "
                    f"ምክንያት፡ {note} "
                    f"እባክዎ በዚሁ አገናኝ በድጋሚ ይላኩ፦ {public_url}"
                )
                send_sms(phone, message)

        from .serializers import ManagerPaymentSerializer
        return Response(ManagerPaymentSerializer(payment, context={'request': request}).data)
