from decimal import Decimal, InvalidOperation
from django.db.models import Sum
from .models import Payment

TOLERANCE = Decimal('1.00')


def to_decimal(v):
    try:
        return None if v in (None, '') else Decimal(str(v))
    except InvalidOperation:
        return None


def amount_due(invoice):
    """What the bidder was told to pay: the letter's fee override if one was set, else the lot total."""
    override = to_decimal((invoice.letterData or {}).get('feeAmount'))
    return override if override and override > 0 else invoice.totalAmount


def remaining_due(invoice, exclude_payment_id=None):
    """Due minus verified partial payments already rejected as 'underpaid'."""
    qs = Payment.objects.filter(
        invoice=invoice, verificationStatus='manager_rejected', amountDiscrepancy='underpaid',
        verifyEtCheck__verified=True, verifyEtCheck__settlementMatched=True,
    )
    if exclude_payment_id:
        qs = qs.exclude(id=exclude_payment_id)
    credited = qs.aggregate(t=Sum('verifyEtCheck__amount'))['t'] or Decimal('0')
    return max(amount_due(invoice) - credited, Decimal('0'))


def classify(paid, remaining):
    """-> ('match'|'underpaid'|'overpaid', positive difference)"""
    diff = Decimal(str(paid)) - Decimal(str(remaining))
    if abs(diff) <= TOLERANCE:
        return 'match', Decimal('0')
    return ('underpaid', -diff) if diff < 0 else ('overpaid', diff)


def refresh_discrepancy(payment, check=None):
    """Sets (does not save) amountDiscrepancy fields from the check.
    Only trusts a check that is verified AND went to our account.
    Returns (kind, difference, remaining)."""
    check = check or getattr(payment, 'verifyEtCheck', None)
    if not check or check.verified is not True or check.settlementMatched is not True or check.amount is None:
        payment.amountDiscrepancy, payment.amountDiscrepancyAmount = '', None
        return '', None, None
    remaining = remaining_due(payment.invoice, exclude_payment_id=payment.id)
    kind, diff = classify(check.amount, remaining)
    payment.amountDiscrepancy = '' if kind == 'match' else kind
    payment.amountDiscrepancyAmount = None if kind == 'match' else diff
    return ('' if kind == 'match' else kind), (None if kind == 'match' else diff), remaining
