"""
Automatic Verify.ET-based approve/reject of bidder-submitted receipts.
Runs ONLY when VerifyEtAutomationSettings.is_enabled() is True, and only
acts on unambiguous results — anything uncertain is left for a human in
the normal manager review queue. Never raises: any failure here must not
break the bidder's receipt upload.
"""
import logging
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .audit import log_audit
from .models import VerifyEtCheck, VerifyEtAutomationSettings
from .sms import send_sms, normalize_phone, public_link
from .verify_et import check_transaction

logger = logging.getLogger(__name__)

AMOUNT_TOLERANCE = Decimal('1.00')  # ETB — small rounding/fee-timing slack, not a loophole


def _amounts_match(verify_amount, invoice_amount):
    if verify_amount is None:
        return False
    try:
        return abs(Decimal(str(verify_amount)) - Decimal(str(invoice_amount))) <= AMOUNT_TOLERANCE
    except (InvalidOperation, TypeError):
        return False


def check_reference_reuse(bank, reference, exclude_payment_id=None):
    """
    Returns (approved_elsewhere, pending_elsewhere).

    Verify.ET's `verified: true` only confirms a real transaction with that
    reference exists somewhere — it says nothing about which invoice it was
    for. So without this, a bidder could resubmit a genuine reference from a
    past, already-settled auction of their own against an unrelated new
    invoice, and the amount would often match too.

    Two severities, because the two cases mean different things:
      approved_elsewhere — reused on a payment already manager_approved. Strong
        signal; this is the dangerous one, since a real reference is being
        claimed a second time for a second invoice.
      pending_elsewhere — reused on a payment still awaiting review. Weaker:
        could be an honest double submission or a bidder who uploaded the
        same receipt twice. Still blocks automatic action (we can't tell them
        apart) but is surfaced to reviewers as a calmer status.

    Both exclude this payment, so re-running a check on the same row doesn't
    flag itself.
    """
    if not bank or not reference:
        return False, False
    from .models import VerifyEtCheck
    qs = VerifyEtCheck.objects.filter(bank=bank, referenceNumber=reference, verified=True)
    if exclude_payment_id:
        qs = qs.exclude(payment_id=exclude_payment_id)
    approved_elsewhere = qs.filter(payment__verificationStatus='manager_approved').exists()
    pending_elsewhere = qs.filter(payment__verificationStatus='pending_manager_review').exists()
    return approved_elsewhere, pending_elsewhere


def process_new_receipt(payment):
    """
    Called once, right after a bidder submits a receipt.

    Always attempts best-effort AI extraction of the bank reference and
    bank, so the manual reviewer gets a pre-filled reference whether or not
    automation is switched on. Extraction must NOT be gated on the toggle —
    it is a reviewer convenience, not an automated action.

    Only proceeds to an automatic Verify.ET check and an approve/reject
    decision when automation is enabled AND an API key exists. Anything
    uncertain is left for a human.

    Returns nothing; all outcomes are visible via the normal Payment /
    VerifyEtCheck / AuditLog rows, never returned to the bidder directly.
    """
    reference, bank, suffix, phone = _get_or_extract_fields(payment)

    if not VerifyEtAutomationSettings.is_enabled():
        return
    if not settings.VERIFY_ET_API_KEY:
        return
    if not reference:
        return  # nothing to check — leave for manual review as usual

    settlement_account = settings.VERIFY_ET_SETTLEMENT_ACCOUNTS.get(bank) if bank else None
    result, error = check_transaction(bank or '', reference, suffix, phone, settlement_account)
    if error or not result:
        logger.info("Auto-verify: Verify.ET check failed for payment #%s: %s", payment.id, error)
        return
    if result.get('processingStatus') != 'completed':
        return  # still queued — a human can re-check later, don't guess

    approved_elsewhere, pending_elsewhere = check_reference_reuse(
        result.get('bank', bank or ''), reference, exclude_payment_id=payment.id,
    )

    VerifyEtCheck.objects.update_or_create(
        payment=payment,
        defaults={
            'bank': result.get('bank', bank or ''),
            'referenceNumber': reference,
            'accountSuffix': suffix,
            'phoneNumber': phone,
            'requestId': result.get('requestId', ''),
            'processingStatus': result['processingStatus'],
            'verified': result.get('verified'),
            'amount': result.get('amount'),
            'currency': result.get('currency', ''),
            'senderName': result.get('senderName', ''),
            'receiverName': result.get('receiverName', ''),
            'receiverAccount': result.get('receiverAccount', ''),
            'settlementMatched': result.get('settlementMatched'),
            'possibleDuplicate': approved_elsewhere,
            'pendingDuplicate': pending_elsewhere,
            'rawResponse': result.get('rawResponse', {}),
            'errorMessage': '',
            'checkedBy': None,  # system action, not a human reviewer
        },
    )

    if approved_elsewhere or pending_elsewhere:
        # Never auto-approve OR auto-reject on a reused reference: a real
        # transaction matching a reused reference can look perfectly valid to
        # Verify.ET while actually belonging to a different invoice. A human
        # has to decide. The check row is already saved above with the flags,
        # so the reviewer sees the warning in the queue.
        logger.warning(
            "Auto-verify: payment #%s reference reused (approved_elsewhere=%s, pending_elsewhere=%s) — leaving for manual review",
            payment.id, approved_elsewhere, pending_elsewhere,
        )
        return

    verified = result.get('verified')
    settlement_matched = result.get('settlementMatched')
    amount_ok = _amounts_match(result.get('amount'), payment.amountPaid)

    if verified is True and settlement_matched is not False and amount_ok:
        _apply_decision(payment, 'approve', reference, result)
    elif (verified is False or settlement_matched is False) and amount_ok:
        _apply_decision(payment, 'reject', reference, result)
    # else: ambiguous — leave for a human, including a rejected-looking result
    # whose amount doesn't line up. Auto-reject also texts the bidder, and a
    # misread reference number would otherwise reject a real payment on the
    # strength of an OCR guess, so both decisions require the amount to match.


def _get_or_extract_fields(payment):
    """Returns (reference, bank, suffix, phone).

    A value the bidder typed themselves always beats one AI guessed off a
    masked receipt image — for a CBE/BoA transfer the account suffix simply
    is not printed, so OCR cannot possibly recover it. Fall back to extraction
    only when the bidder didn't supply a reference.
    """
    if payment.bidderReferenceNumber:
        return (
            payment.bidderReferenceNumber,
            payment.bidderBank or '',
            payment.bidderAccountSuffix or '',
            payment.bidderPhoneNumber or '',
        )
    extraction = getattr(payment, 'extraction', None)
    if extraction is None and settings.GEMINI_API_KEY and payment.receiptFile:
        from .receipt_extraction import run_and_save_extraction
        try:
            extraction, err = run_and_save_extraction(payment, user=None)
            if err:
                extraction = None
        except Exception:
            logger.exception("Auto-verify: extraction failed for payment #%s", payment.id)
            extraction = None
    if not extraction:
        return None, '', '', ''
    return (
        extraction.bankReferenceNumber or '',
        extraction.detectedBank or '',
        '',  # accountSuffix isn't reliably extractable — masked on receipts,
             # and the bidder-typed value above is the only trustworthy source
        getattr(extraction, 'detectedPhoneNumber', '') or '',
    )


def _apply_decision(payment, decision, reference, verify_result):
    invoice = payment.invoice
    previous_status = invoice.status
    note = (
        f"Auto-{'approved' if decision == 'approve' else 'rejected'} by Verify.ET "
        f"(ref {reference}, verified={verify_result.get('verified')}, "
        f"settlementMatched={verify_result.get('settlementMatched')})."
    )

    with transaction.atomic():
        payment.autoReviewed = True
        payment.managerVerifiedDate = timezone.now()
        payment.managerNote = note

        if decision == 'approve':
            payment.verificationStatus = 'manager_approved'
            payment.paymentStatus = 'verified'
            payment.verifiedDate = timezone.now()
            invoice.status = 'paid'
        else:
            payment.verificationStatus = 'manager_rejected'
            invoice.status = 'pending_payment'

        payment.save(update_fields=[
            'autoReviewed', 'verificationStatus', 'managerVerifiedDate', 'managerNote',
            'paymentStatus', 'verifiedDate',
        ])
        invoice.save(update_fields=['status', 'updatedAt'])

        log_audit(
            invoice,
            f"Receipt {'approved' if decision == 'approve' else 'rejected'} automatically (Verify.ET)",
            user=None, previous_value=previous_status, new_value=invoice.status,
            reason=note, action_type='auto_verify_et',
        )

    if decision == 'reject':
        winner = invoice.winner
        phone = normalize_phone(winner.winnerPhone)
        if phone:
            name = winner.bidderNameAmharic or winner.bidderName
            message = (
                f"ውድ {name}፣ የላኩት የክፍያ ደረሰኝ በራስ-ሰር ማረጋገጫ ውድቅ ተደርጓል። "
                f"እባክዎ በዚሁ አገናኝ በድጋሚ ይላኩ፦ {public_link(invoice)}"
            )
            send_sms(phone, message)
