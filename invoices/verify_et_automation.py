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


def maybe_auto_verify(payment):
    """
    Called once, right after a bidder submits a receipt. Best-effort:
    - Runs AI extraction to find a reference number + likely bank (if
      GEMINI_API_KEY is set).
    - If a reference was found, checks it with Verify.ET.
    - Auto-approves or auto-rejects ONLY on an unambiguous result.
    Returns nothing; all outcomes are visible via the normal Payment/
    VerifyEtCheck/AuditLog rows, never returned to the bidder directly.
    """
    if not VerifyEtAutomationSettings.is_enabled():
        return
    if not settings.VERIFY_ET_API_KEY:
        return

    reference, bank, suffix, phone = _get_or_extract_fields(payment)
    if not reference:
        return  # nothing to check — leave for manual review as usual

    settlement_account = settings.VERIFY_ET_SETTLEMENT_ACCOUNTS.get(bank) if bank else None
    result, error = check_transaction(bank or '', reference, suffix, phone, settlement_account)
    if error or not result:
        logger.info("Auto-verify: Verify.ET check failed for payment #%s: %s", payment.id, error)
        return
    if result.get('processingStatus') != 'completed':
        return  # still queued — a human can re-check later, don't guess

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
            'rawResponse': result.get('rawResponse', {}),
            'errorMessage': '',
            'checkedBy': None,  # system action, not a human reviewer
        },
    )

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
    """Returns (reference, bank, suffix, phone) — from an existing extraction
    if present, else runs one now (best-effort, never raises)."""
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
        '',  # accountSuffix isn't reliably extractable yet — left blank on purpose
        '',
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
