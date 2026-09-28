"""Receipt processing: always extract; only auto-decide when an admin enabled automation.
Approve only if verified + money reached OUR account + amount matches. Anything else waits for a human."""
import logging
import threading
import time

from django.conf import settings
from django.db import close_old_connections, transaction
from django.db.models import Q
from django.utils import timezone

from .audit import log_audit
from .models import Payment, VerifyEtAutomationSettings, VerifyEtCheck
from .payment_amounts import refresh_discrepancy
from .sms import build_rejection_message, normalize_phone, send_sms
from .verify_et import check_transaction, fetch_status

logger = logging.getLogger(__name__)
POLL_ATTEMPTS, POLL_SECONDS = 6, 5


def check_reference_reuse(reference, exclude_payment_id=None):
    """(used_elsewhere_strong, pending_elsewhere). 'Strong' = approved elsewhere, OR already
    credited as a verified partial payment (rejected as underpaid) - so one transaction can
    never be counted twice."""
    if not reference:
        return False, False
    qs = VerifyEtCheck.objects.filter(bank__iexact='cbe', referenceNumber=reference, verified=True)
    if exclude_payment_id:
        qs = qs.exclude(payment_id=exclude_payment_id)
    strong = qs.filter(
        Q(payment__verificationStatus='manager_approved')
        | Q(payment__verificationStatus='manager_rejected', payment__amountDiscrepancy='underpaid')
    ).exists()
    pending = qs.filter(payment__verificationStatus='pending_manager_review').exists()
    return strong, pending


def persist_check(payment, result, reference, suffix, checked_by):
    strong, pending = check_reference_reuse(reference, exclude_payment_id=payment.id)
    check, _ = VerifyEtCheck.objects.update_or_create(
        payment=payment,
        defaults={
            'bank': 'cbe', 'referenceNumber': reference, 'accountSuffix': suffix, 'phoneNumber': '',
            'requestId': result.get('requestId', ''),
            'processingStatus': result.get('processingStatus', ''),
            'verified': result.get('verified'), 'amount': result.get('amount'),
            'currency': result.get('currency', ''), 'senderName': result.get('senderName', ''),
            'receiverName': result.get('receiverName', ''), 'receiverAccount': result.get('receiverAccount', ''),
            'settlementMatched': result.get('settlementMatched'),
            'rawResponse': result.get('rawResponse', {}), 'errorMessage': result.get('errorMessage', ''),
            'possibleDuplicate': strong, 'pendingDuplicate': pending, 'checkedBy': checked_by,
        },
    )
    if check.processingStatus == 'completed':
        refresh_discrepancy(payment, check)
        payment.save(update_fields=['amountDiscrepancy', 'amountDiscrepancyAmount'])
    return check


def decide(check, payment):
    """Pure decision -> ('approve'|'reject'|None, reason)."""
    if check.possibleDuplicate or check.pendingDuplicate:
        return None, 'reference already used elsewhere'
    if check.verified is not True or check.amount is None:
        return None, 'not verified'
    if check.settlementMatched is False:
        return 'reject', 'money went to a different account'
    if check.settlementMatched is not True:
        return None, 'could not confirm the receiving account'
    if payment.amountDiscrepancy == '':
        return 'approve', 'verified, our account, amount matches'
    if payment.amountDiscrepancy == 'underpaid':
        return 'reject', 'underpaid'
    return None, 'overpaid - needs a human'


def _get_or_extract(payment):
    extraction = getattr(payment, 'extraction', None)
    if extraction is None and settings.GEMINI_API_KEY and payment.receiptFile:
        from .receipt_extraction import run_and_save_extraction
        try:
            extraction, err = run_and_save_extraction(payment, user=None)
            if err:
                extraction = None
        except Exception:
            logger.exception('Extraction failed for payment #%s', payment.id)
            extraction = None
    if not extraction:
        return '', ''
    return extraction.bankReferenceNumber or '', (extraction.detectedBank or '').lower()


def _poll(check, payment):
    account = settings.VERIFY_ET_SETTLEMENT_ACCOUNTS.get('cbe')
    for _ in range(POLL_ATTEMPTS):
        url = (check.rawResponse or {}).get('statusUrl')
        if not url or check.processingStatus in ('completed', 'failed'):
            break
        time.sleep(POLL_SECONDS)
        result, error = fetch_status(url, account)
        if result and not error:
            check = persist_check(payment, result, check.referenceNumber, check.accountSuffix, None)
    return check


def process_new_receipt(payment):
    reference, detected_bank = _get_or_extract(payment)       # always, for reviewer convenience
    if not VerifyEtAutomationSettings.is_enabled() or not settings.VERIFY_ET_API_KEY or not reference:
        return
    if detected_bank not in ('', 'cbe'):
        return                                                 # not a CBE receipt: human handles it
    account = settings.VERIFY_ET_SETTLEMENT_ACCOUNTS.get('cbe')
    suffix = settings.VERIFY_ET_CBE_SUFFIX
    result, error = check_transaction(reference, suffix, account, wait_ms=8000)
    if error or not result:
        logger.info('Auto-verify failed for payment #%s: %s', payment.id, error)
        return
    check = persist_check(payment, result, reference, suffix, None)
    if check.processingStatus != 'completed' and settings.VERIFY_ET_PROCESS_ASYNC:
        check = _poll(check, payment)
    if check.processingStatus != 'completed':
        return
    decision, reason = decide(check, payment)
    if decision:
        _apply_decision(payment, check, decision, reason)


def _apply_decision(payment, check, decision, reason):
    invoice = payment.invoice
    previous = invoice.status
    approve = decision == 'approve'
    note = (f"Auto-{'approved' if approve else 'rejected'} by Verify.ET: {reason} "
            f"(ref {check.referenceNumber}, paid {check.amount}, flag {payment.amountDiscrepancy or 'none'}).")
    with transaction.atomic():
        payment.autoReviewed = True
        payment.managerVerifiedDate = timezone.now()
        payment.managerNote = note
        if approve:
            payment.verificationStatus, payment.paymentStatus = 'manager_approved', 'verified'
            payment.verifiedDate, payment.amountPaid = timezone.now(), check.amount
            invoice.status = 'paid'
        else:
            payment.verificationStatus = 'manager_rejected'
            invoice.status = 'pending_payment'
        payment.save(update_fields=['autoReviewed', 'verificationStatus', 'managerVerifiedDate', 'managerNote',
                                    'paymentStatus', 'verifiedDate', 'amountPaid'])
        invoice.save(update_fields=['status', 'updatedAt'])
        log_audit(invoice, f"Receipt {'approved' if approve else 'rejected'} automatically (Verify.ET)", None,
                  previous, invoice.status, reason=note, action_type='auto_verify_et')
    if not approve:
        phone = normalize_phone(invoice.winner.winnerPhone)
        if phone:
            remaining = payment.amountDiscrepancyAmount if payment.amountDiscrepancy == 'underpaid' else None
            send_sms(phone, build_rejection_message(invoice, remaining=remaining,
                                                     wrong_account=check.settlementMatched is False))


def dispatch_receipt_processing(payment):
    """Called by the public upload view. Async by default so the bidder isn't kept waiting."""
    if not settings.VERIFY_ET_PROCESS_ASYNC:
        try:
            process_new_receipt(payment)
        except Exception:
            logger.exception('Receipt processing failed (non-fatal)')
        return
    payment_id = payment.id

    def job():
        try:
            p = Payment.objects.select_related('invoice', 'invoice__winner').get(pk=payment_id)
            process_new_receipt(p)
        except Exception:
            logger.exception('Background receipt processing failed (non-fatal)')
        finally:
            close_old_connections()

    threading.Thread(target=job, daemon=True).start()
