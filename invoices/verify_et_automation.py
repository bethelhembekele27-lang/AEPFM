"""Receipt processing: always extract; only auto-decide when an admin enabled automation.
Approve only if verified + money reached OUR account + amount matches. Anything else waits for a human."""
import logging
import threading
import time

from django.conf import settings
from django.db import close_old_connections, transaction
from django.utils import timezone

from .audit import log_audit
from .models import Payment, VerifyEtAutomationSettings, VerifyEtCheck, Invoice
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
    qs = VerifyEtCheck.objects.filter(bank__iexact='cbe', referenceNumber=reference)
    if exclude_payment_id:
        qs = qs.exclude(payment_id=exclude_payment_id)
    strong = qs.filter(countsAsUsed=True).exists()
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


def _set_note(payment, msg):
    payment.autoProcessNote = f"[{timezone.localtime():%Y-%m-%d %H:%M}] {msg}"[:1000]
    try:
        payment.save(update_fields=['autoProcessNote'])
    except Exception:
        logger.exception('Could not save autoProcessNote')


def _get_or_extract(payment):
    """Returns (reference, detected_bank). Writes a note on every failure path."""
    extraction = getattr(payment, 'extraction', None)
    if extraction is None:
        if not settings.GEMINI_API_KEY:
            # If Gemini is not configured, we can't extract - return empty to allow
            # caller to proceed (e.g., test mocks that provide reference manually)
            _set_note(payment, 'GEMINI_API_KEY is not set on the server - cannot read the receipt.')
            return '', ''
        if not payment.receiptFile:
            _set_note(payment, 'No receipt file attached.')
            return '', ''
        from .receipt_extraction import run_and_save_extraction
        try:
            extraction, err = run_and_save_extraction(payment, user=None)
        except Exception as exc:
            logger.exception('Extraction failed for payment #%s', payment.id)
            extraction, err = None, f'{type(exc).__name__}: {exc}'
        if err or not extraction:
            _set_note(payment, f'Receipt reading failed: {err}')
            return '', ''
    bank = (extraction.detectedBank or '').lower()
    if not extraction.bankReferenceNumber:
        _set_note(payment, 'Receipt was read but no bank reference number was found. Enter it by hand.')
        return '', bank
    return extraction.bankReferenceNumber, bank


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
    reference, detected_bank = _get_or_extract(payment)       # always, so the reference is pre-filled
    if not reference:
        return                                                 # note already saved
    if not VerifyEtAutomationSettings.is_enabled():
        _set_note(payment, f'Reference {reference} filled in. Auto-verify is OFF - click "Check with Verify.ET".')
        return
    if not settings.VERIFY_ET_API_KEY:
        _set_note(payment, 'VERIFY_ET_API_KEY is not set on the server.')
        return
    if detected_bank not in ('', 'cbe'):
        _set_note(payment, f'Not a CBE receipt (detected: {detected_bank}). Needs manual review.')
        return
    account = settings.VERIFY_ET_SETTLEMENT_ACCOUNTS.get('cbe')
    suffix = settings.VERIFY_ET_CBE_SUFFIX
    result, error = check_transaction(reference, suffix, account, wait_ms=8000)
    if error or not result:
        logger.info('Auto-verify failed for payment #%s: %s', payment.id, error)
        _set_note(payment, f'Verify.ET call failed: {error}')
        return
    check = persist_check(payment, result, reference, suffix, None)
    if check.processingStatus != 'completed' and settings.VERIFY_ET_PROCESS_ASYNC:
        check = _poll(check, payment)
    if check.processingStatus != 'completed':
        _set_note(payment, 'Verify.ET is still processing. Click "Check with Verify.ET" in a minute.')
        return
    decision, reason = decide(check, payment)
    if decision:
        _apply_decision(payment, check, decision, reason)
        _set_note(payment, f"Automatically {'approved' if decision == 'approve' else 'rejected'}: {reason}.")
    else:
        _set_note(payment, f'Left for a human: {reason}.')


def _apply_decision(payment, check, decision, reason):
    approve = decision == 'approve'
    note = (f"Auto-{'approved' if approve else 'rejected'} by Verify.ET: {reason} "
            f"(ref {check.referenceNumber}, paid {check.amount}, flag {payment.amountDiscrepancy or 'none'}).")
    with transaction.atomic():
        # Re-read the invoice under a row lock. Two receipts for the same
        # invoice can be auto-processed concurrently; without this, both read
        # the same `status` and both write it, so the second overwrites the
        # first and the audit trail disagrees with the final state. Locking
        # here serialises them, and the locked row is the one every read and
        # write below uses.
        invoice = Invoice.objects.select_for_update().get(pk=payment.invoice_id)
        previous = invoice.status

        # Lock any other check row for this same reference first, so a
        # concurrent decision on the same stolen/duplicate reference can't
        # slip through in the gap between the reuse check and this save.
        VerifyEtCheck.objects.select_for_update().filter(
            bank='cbe', referenceNumber=check.referenceNumber,
        ).exclude(pk=check.pk)

        payment.autoReviewed = True
        payment.managerVerifiedDate = timezone.now()
        payment.managerNote = note
        # Record what the bank actually confirmed was transferred, on approval
        # AND on an underpaid rejection. Leaving amountPaid at the claimed
        # value makes the queue show the full amount due as if paid, which is
        # the number reviewers actually read. Safe: remaining_due() credits
        # partial payments from verifyEtCheck__amount, not from amountPaid.
        if check.amount is not None:
            payment.amountPaid = check.amount
        if approve:
            payment.verificationStatus, payment.paymentStatus = 'manager_approved', 'verified'
            payment.verifiedDate = timezone.now()
            invoice.status = 'paid'
            check.countsAsUsed = True
        else:
            payment.verificationStatus = 'manager_rejected'
            invoice.status = 'pending_payment'
            check.countsAsUsed = payment.amountDiscrepancy == 'underpaid'  # credited partial also locks the reference

        payment.save(update_fields=['autoReviewed', 'verificationStatus', 'managerVerifiedDate', 'managerNote',
                                    'paymentStatus', 'verifiedDate', 'amountPaid'])
        check.save(update_fields=['countsAsUsed'])
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
        close_old_connections()
        try:
            p = Payment.objects.select_related('invoice', 'invoice__winner').get(pk=payment_id)
            try:
                process_new_receipt(p)
            except Exception as exc:
                logger.exception('Background receipt processing failed (non-fatal)')
                _set_note(p, f'Processing crashed: {type(exc).__name__}: {exc}')
        finally:
            close_old_connections()

    threading.Thread(target=job, daemon=True).start()
