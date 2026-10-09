from django.db import transaction
from django.utils import timezone
from django.conf import settings
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status as http_status
from rest_framework.throttling import UserRateThrottle

from invoices.models import Payment, VerifyEtCheck
from invoices.permissions import has_permission
from invoices.audit import log_audit
from invoices.services.sms import send_sms, normalize_phone, public_link
from invoices.services.payment_amounts import refresh_discrepancy
from invoices.services.verify_et_automation import persist_check
from invoices.services.sms import build_rejection_message

logger = logging.getLogger(__name__)


class VerifyEtCheckThrottle(UserRateThrottle):
    scope = 'verify_et_check'


class VerifyEtRefreshThrottle(UserRateThrottle):
    scope = 'verify_et_refresh'


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
        can_manage = has_permission(request.user, 'manager_verify_receipt')
        can_view_approved = has_permission(request.user, 'verify_payment')
        if not (can_manage or can_view_approved):
            return Response({'error': 'Permission denied'}, status=http_status.HTTP_403_FORBIDDEN)

        status_filter = request.query_params.get('verificationStatus', 'pending_manager_review')
        # Finance-only users can never fetch pending/rejected via the API directly,
        # even if they hand-craft the request — defense in depth beyond just hiding
        # the tabs in ManagerReview.jsx.
        if not can_manage and can_view_approved:
            status_filter = 'manager_approved'

        qs = (
            Payment.objects
            .filter(verificationStatus=status_filter, submittedViaPublicLink=True)
            .select_related('invoice', 'invoice__winner')
            .order_by('-uploadedAt')
        )

        # Import here to avoid a circular-import at module level
        from invoices.serializers import ManagerPaymentSerializer
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
        kind, diff, check = '', None, None

        with transaction.atomic():
            kind, diff, remaining = refresh_discrepancy(payment)
            check = getattr(payment, 'verifyEtCheck', None)
            if check:
                VerifyEtCheck.objects.select_for_update().filter(
                    bank=check.bank, referenceNumber=check.referenceNumber,
                ).exclude(pk=check.pk)

            payment.managerVerifiedBy = request.user
            payment.managerVerifiedDate = timezone.now()
            payment.managerNote = note

            # Record what the bank actually confirmed was transferred, not just
            # the amount the bidder claimed. Applies to approvals AND to
            # underpaid rejections — otherwise the row keeps showing the full
            # amount due as though it had been paid, which is exactly the
            # number a reviewer glances at. Only trust a check that is
            # verified and confirmed to our own account; the discrepancy
            # fields (computed from verifyEtCheck.amount) are unaffected
            # either way since remaining_due credits from the check, not here.
            if check and check.amount is not None and check.verified is True and check.settlementMatched is True:
                payment.amountPaid = check.amount

            if decision == 'approve':
                payment.verificationStatus = 'manager_approved'
                payment.paymentStatus = 'verified'
                payment.verifiedBy = request.user
                payment.verifiedDate = timezone.now()
                if check:
                    check.countsAsUsed = True
                    check.save(update_fields=['countsAsUsed'])
                invoice.status = 'paid'
                log_audit(
                    invoice,
                    'Receipt approved by manager (auto-marked paid)',
                    request.user,
                    previous_status,
                    invoice.status,
                    reason=note,
                    action_type='other',
                )
            else:
                payment.verificationStatus = 'manager_rejected'
                invoice.status = 'pending_payment'
                if check and kind == 'underpaid':
                    check.countsAsUsed = True
                    check.save(update_fields=['countsAsUsed'])
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
                'verificationStatus', 'managerVerifiedBy', 'managerVerifiedDate',
                'managerNote', 'paymentStatus', 'verifiedBy', 'verifiedDate',
                'amountDiscrepancy', 'amountDiscrepancyAmount', 'amountPaid',
            ])
            invoice.save(update_fields=['status', 'updatedAt'])

        # Send SMS on rejection so the bidder knows to resubmit
        if decision == 'reject':
            phone = normalize_phone(invoice.winner.winnerPhone)
            if phone:
                owed = diff if kind == 'underpaid' else None   # never mention overpayment
                send_sms(phone, build_rejection_message(
                    invoice, note=note, remaining=owed,
                    wrong_account=bool(check and check.settlementMatched is False)))

        if decision == 'approve' and settings.GEMINI_API_KEY:
            from invoices.services.receipt_extraction import run_and_save_extraction
            try:
                run_and_save_extraction(payment, request.user)
            except Exception:
                logger.exception('Auto-extraction after approval failed (non-fatal)')
            # Deliberately never re-raised — the approval already succeeded and
            # committed; a broken/rate-limited AI call must never look like a
            # failed approval to the reviewer.

        from invoices.serializers import ManagerPaymentSerializer
        return Response(ManagerPaymentSerializer(payment, context={'request': request}).data)


class ReceiptExtractView(APIView):
    """
    POST /api/receipts/<payment_id>/extract/
    Manual trigger only — never automatic. Only works on a receipt that
    is already manager_approved (record-keeping/auto-fill, not a
    pre-approval decision aid). Re-running overwrites the previous
    extraction for this payment.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, payment_id):
        if not (has_permission(request.user, 'manager_verify_receipt')
                or has_permission(request.user, 'verify_payment')):
            return Response({'error': 'Permission denied'}, status=http_status.HTTP_403_FORBIDDEN)

        try:
            payment = Payment.objects.select_related('invoice').get(pk=payment_id)
        except Payment.DoesNotExist:
            return Response({'error': 'Payment not found'}, status=http_status.HTTP_404_NOT_FOUND)

        if payment.verificationStatus != 'manager_approved':
            return Response(
                {'error': 'AI extraction only runs on receipts that are already approved.'},
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        if not payment.receiptFile:
            return Response({'error': 'This payment has no receipt file.'}, status=http_status.HTTP_400_BAD_REQUEST)

        from invoices.services.receipt_extraction import run_and_save_extraction
        extraction, error = run_and_save_extraction(payment, request.user)
        if error:
            return Response({'error': error}, status=http_status.HTTP_502_BAD_GATEWAY)

        from invoices.serializers import ReceiptExtractionSerializer
        return Response(ReceiptExtractionSerializer(extraction).data, status=http_status.HTTP_201_CREATED)


class VerifyEtCheckView(APIView):
    """POST /api/receipts/<id>/verify-transaction/ {referenceNumber, accountSuffix?}
    CBE only; always checks the money reached OUR account."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [VerifyEtCheckThrottle]

    def post(self, request, payment_id):
        if not (has_permission(request.user, 'manager_verify_receipt') or has_permission(request.user, 'verify_payment')):
            return Response({'error': 'Permission denied'}, status=403)
        try:
            payment = Payment.objects.select_related('invoice').get(pk=payment_id)
        except Payment.DoesNotExist:
            return Response({'error': 'Payment not found'}, status=404)
        reference = (request.data.get('referenceNumber') or '').strip()
        suffix = (request.data.get('accountSuffix') or '').strip() or settings.VERIFY_ET_CBE_SUFFIX
        if not reference:
            return Response({'error': 'A reference number is required.'}, status=400)
        from invoices.services.verify_et import check_transaction
        result, error = check_transaction(reference, suffix, settings.VERIFY_ET_SETTLEMENT_ACCOUNTS.get('cbe'))
        if error:
            return Response({'error': error}, status=502)
        from invoices.serializers import VerifyEtCheckSerializer
        check = persist_check(payment, result, reference, suffix, request.user)
        return Response(VerifyEtCheckSerializer(check).data, status=201)


class VerifyEtRefreshView(APIView):
    """POST /api/receipts/<id>/verify-transaction/refresh/ - follow up a queued check."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [VerifyEtRefreshThrottle]

    def post(self, request, payment_id):
        if not (has_permission(request.user, 'manager_verify_receipt') or has_permission(request.user, 'verify_payment')):
            return Response({'error': 'Permission denied'}, status=403)
        try:
            payment = Payment.objects.select_related('invoice').get(pk=payment_id)
            check = payment.verifyEtCheck
        except (Payment.DoesNotExist, VerifyEtCheck.DoesNotExist):
            return Response({'error': 'No check found for this payment.'}, status=404)
        from invoices.serializers import VerifyEtCheckSerializer
        if check.processingStatus == 'completed':
            return Response(VerifyEtCheckSerializer(check).data)
        url = (check.rawResponse or {}).get('statusUrl')
        if not url:
            return Response({'error': 'No pending check to refresh.'}, status=400)
        from invoices.services.verify_et import fetch_status
        result, error = fetch_status(url, settings.VERIFY_ET_SETTLEMENT_ACCOUNTS.get('cbe'))
        if error:
            return Response({'error': error}, status=502)
        check = persist_check(payment, result, check.referenceNumber, check.accountSuffix, request.user)
        return Response(VerifyEtCheckSerializer(check).data)


class ReceiptReprocessView(APIView):
    """POST /api/receipts/<id>/reprocess/ - re-run extraction (+ Verify.ET/decision if automation is on), synchronously."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [VerifyEtCheckThrottle]

    def post(self, request, payment_id):
        if not (has_permission(request.user, 'manager_verify_receipt') or has_permission(request.user, 'verify_payment')):
            return Response({'error': 'Permission denied'}, status=403)
        try:
            payment = Payment.objects.select_related('invoice', 'invoice__winner').get(pk=payment_id)
        except Payment.DoesNotExist:
            return Response({'error': 'Payment not found'}, status=404)
        if payment.verificationStatus != 'pending_manager_review':
            return Response({'error': 'Only receipts still pending review can be re-processed.'}, status=400)
        from invoices.services.verify_et_automation import process_new_receipt, _set_note
        try:
            process_new_receipt(payment)
        except Exception as exc:
            logger.exception('Reprocess failed')
            _set_note(payment, f'Processing crashed: {type(exc).__name__}: {exc}')
        payment = Payment.objects.select_related('invoice', 'invoice__winner').get(pk=payment_id)
        from invoices.serializers import ManagerPaymentSerializer
        return Response(ManagerPaymentSerializer(payment, context={'request': request}).data)
