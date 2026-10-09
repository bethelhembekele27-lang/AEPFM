"""
One function per report type. Each returns (title, periodLabel, columns, rows, total)
where columns is [{key, label}, ...] and rows is a list of plain dicts matching
those keys — this lets the frontend render any report type generically with
one table component, instead of hardcoding a column set per report.

PERIOD SEMANTICS — the ambiguous part, decided explicitly here so it's easy
to correct later instead of silently guessing:
- "outstanding" and "overdue" filter by dueDate (these are about what's owed,
  as of when it was due).
- "daily"/"monthly" collections and "verification" filter by the underlying
  Payment.verifiedDate (these are about when money actually moved).
- "by-auction"/"by-client" (revenue) filter by Payment.verifiedDate too, and
  only count PAID invoices — "revenue" means collected, not merely invoiced.
- dateFrom/dateTo, if provided, always override the period dropdown entirely
  for whichever date field that report type uses.
"""
from datetime import timedelta
from decimal import Decimal
from django.db.models import Sum, Count, F
from django.utils import timezone

from invoices.models import Invoice, InvoiceLot, Payment, Auction, Winner

OUTSTANDING_STATUSES = ['invoice_generated', 'pending_payment', 'payment_submitted', 'under_verification', 'overdue']

PERIOD_LABELS = {'today': 'Today', 'week': 'This week', 'month': 'This month', 'year': 'This year', 'custom': 'Custom range'}


def _period_bounds(filters):
    """Returns (start_date, end_date, label). Custom dateFrom/dateTo wins if given."""
    date_from = filters.get('dateFrom')
    date_to = filters.get('dateTo')
    if date_from or date_to:
        return date_from, date_to, PERIOD_LABELS['custom']

    period = filters.get('period', 'month')
    today = timezone.localdate()
    if period == 'today':
        return today, today, PERIOD_LABELS['today']
    if period == 'week':
        return today - timedelta(days=today.weekday()), today, PERIOD_LABELS['week']
    if period == 'year':
        return today.replace(month=1, day=1), today, PERIOD_LABELS['year']
    # default: month
    return today.replace(day=1), today, PERIOD_LABELS['month']


def _apply_common_invoice_filters(qs, filters):
    """clientCompany / importBatch / auction — shared across the invoice-row report types."""
    if filters.get('clientCompany'):
        qs = qs.filter(winner__companyName__icontains=filters['clientCompany'])
    if filters.get('importBatch'):
        qs = qs.filter(importBatch_id=filters['importBatch'])
    if filters.get('auction'):
        qs = qs.filter(lots__auctionName__icontains=filters['auction']).distinct()
    return qs


def _invoice_rows(qs):
    rows = []
    for inv in qs.select_related('winner'):
        rows.append({
            'invoiceNumber': inv.invoiceNumber,
            'bidderName': inv.winner.bidderName,
            'companyName': inv.winner.companyName or '—',
            'amount': str(inv.totalAmount),
            'dueDate': str(inv.dueDate),
            'status': inv.status,
        })
    return rows


INVOICE_COLUMNS = [
    {'key': 'invoiceNumber', 'label': 'Invoice #'},
    {'key': 'bidderName', 'label': 'Bidder'},
    {'key': 'companyName', 'label': 'Company'},
    {'key': 'amount', 'label': 'Amount'},
    {'key': 'dueDate', 'label': 'Due date'},
    {'key': 'status', 'label': 'Status'},
]


def run_outstanding(filters):
    """
    Outstanding is a point-in-time snapshot ("what's owed right now"), not
    a period-bounded activity report. The period DROPDOWN (today/week/
    month/year) does NOT restrict this report at all — an invoice that's
    been outstanding since 3 months ago should still show up under "this
    month" selected, otherwise the report actively hides the oldest,
    most-important-to-chase invoices. Confirmed this is actually needed
    by testing: filtering by either dueDate or invoiceDate against the
    period dropdown made a genuinely outstanding invoice disappear.
    Only an EXPLICIT dateFrom/dateTo (the user deliberately narrowing by
    invoiceDate) restricts anything here.
    """
    date_from = filters.get('dateFrom')
    date_to = filters.get('dateTo')
    label = PERIOD_LABELS['custom'] if (date_from or date_to) else 'All outstanding, as of today'
    qs = Invoice.objects.filter(status__in=OUTSTANDING_STATUSES)
    if filters.get('paymentStatus'):
        qs = qs.filter(status__in=filters['paymentStatus'])
    if date_from:
        qs = qs.filter(invoiceDate__gte=date_from)
    if date_to:
        qs = qs.filter(invoiceDate__lte=date_to)
    qs = _apply_common_invoice_filters(qs, filters)
    rows = _invoice_rows(qs)
    total = sum((Decimal(r['amount']) for r in rows), Decimal('0.00'))
    return 'Outstanding processing fees', label, INVOICE_COLUMNS, rows, total


def run_overdue(filters):
    """Same point-in-time reasoning as run_outstanding above — no default
    period restriction, only explicit dateFrom/dateTo narrows it."""
    date_from = filters.get('dateFrom')
    date_to = filters.get('dateTo')
    label = PERIOD_LABELS['custom'] if (date_from or date_to) else 'All overdue, as of today'
    qs = Invoice.objects.filter(status='overdue')
    if date_from:
        qs = qs.filter(invoiceDate__gte=date_from)
    if date_to:
        qs = qs.filter(invoiceDate__lte=date_to)
    qs = _apply_common_invoice_filters(qs, filters)
    today = timezone.localdate()
    rows = []
    for inv in qs.select_related('winner'):
        rows.append({
            'invoiceNumber': inv.invoiceNumber,
            'bidderName': inv.winner.bidderName,
            'companyName': inv.winner.companyName or '—',
            'amount': str(inv.totalAmount),
            'dueDate': str(inv.dueDate),
            'daysOverdue': (today - inv.dueDate).days,
        })
    rows.sort(key=lambda r: -r['daysOverdue'])  # oldest/most-overdue first
    total = sum((Decimal(r['amount']) for r in rows), Decimal('0.00'))
    columns = INVOICE_COLUMNS[:-1] + [{'key': 'daysOverdue', 'label': 'Days overdue'}]
    return 'Overdue payments report', label, columns, rows, total


def _payment_qs(filters, status_filter):
    qs = Payment.objects.filter(paymentStatus=status_filter).select_related('invoice', 'invoice__winner', 'verifiedBy')
    if filters.get('clientCompany'):
        qs = qs.filter(invoice__winner__companyName__icontains=filters['clientCompany'])
    if filters.get('importBatch'):
        qs = qs.filter(invoice__importBatch_id=filters['importBatch'])
    return qs


def run_daily_collections(filters):
    filters = {**filters, 'period': 'today'} if not (filters.get('dateFrom') or filters.get('dateTo')) else filters
    start, end, label = _period_bounds(filters)
    qs = _payment_qs(filters, 'verified')
    if start:
        qs = qs.filter(verifiedDate__date__gte=start)
    if end:
        qs = qs.filter(verifiedDate__date__lte=end)
    rows = [{
        'invoiceNumber': p.invoice.invoiceNumber, 'bidderName': p.invoice.winner.bidderName,
        'amount': str(p.amountPaid), 'method': p.get_paymentMethod_display(),
        'verifiedDate': p.verifiedDate.strftime('%Y-%m-%d %H:%M') if p.verifiedDate else '',
    } for p in qs]
    total = sum((Decimal(r['amount']) for r in rows), Decimal('0.00'))
    columns = [{'key': 'invoiceNumber', 'label': 'Invoice #'}, {'key': 'bidderName', 'label': 'Bidder'},
               {'key': 'amount', 'label': 'Amount'}, {'key': 'method', 'label': 'Method'},
               {'key': 'verifiedDate', 'label': 'Verified at'}]
    return 'Daily collections', label, columns, rows, total


def run_monthly_collections(filters):
    filters = {**filters, 'period': 'month'} if not (filters.get('dateFrom') or filters.get('dateTo')) else filters
    title, _, columns, rows, total = run_daily_collections(filters)
    return 'Monthly collections', PERIOD_LABELS['month'], columns, rows, total


def run_verification(filters):
    start, end, label = _period_bounds(filters)
    qs = Payment.objects.exclude(paymentStatus='pending').select_related('invoice', 'invoice__winner', 'verifiedBy')
    if filters.get('paymentStatus'):
        # here paymentStatus filter means Payment.paymentStatus (verified/rejected), not Invoice.status
        qs = qs.filter(paymentStatus__in=filters['paymentStatus'])
    if start:
        qs = qs.filter(verifiedDate__date__gte=start)
    if end:
        qs = qs.filter(verifiedDate__date__lte=end)
    rows = [{
        'invoiceNumber': p.invoice.invoiceNumber, 'bidderName': p.invoice.winner.bidderName,
        'amount': str(p.amountPaid), 'result': p.get_paymentStatus_display(),
        'reviewer': (p.verifiedBy.get_full_name() or p.verifiedBy.get_username()) if p.verifiedBy else '—',
        'verifiedDate': p.verifiedDate.strftime('%Y-%m-%d %H:%M') if p.verifiedDate else '',
    } for p in qs]
    total = sum((Decimal(r['amount']) for r in rows), Decimal('0.00'))
    columns = [{'key': 'invoiceNumber', 'label': 'Invoice #'}, {'key': 'bidderName', 'label': 'Bidder'},
               {'key': 'amount', 'label': 'Amount'}, {'key': 'result', 'label': 'Result'},
               {'key': 'reviewer', 'label': 'Reviewer'}, {'key': 'verifiedDate', 'label': 'Verified at'}]
    return 'Payment verification report', label, columns, rows, total


def _revenue_qs(filters):
    start, end, label = _period_bounds(filters)
    qs = InvoiceLot.objects.filter(invoice__status='paid').select_related('invoice__winner', 'invoice__winner__auction')
    payments = Payment.objects.filter(paymentStatus='verified')
    if start:
        payments = payments.filter(verifiedDate__date__gte=start)
    if end:
        payments = payments.filter(verifiedDate__date__lte=end)
    paid_invoice_ids = payments.values_list('invoice_id', flat=True)
    qs = qs.filter(invoice_id__in=paid_invoice_ids)
    return qs, label


def run_by_auction(filters):
    qs, label = _revenue_qs(filters)
    agg = qs.values('auctionName').annotate(total=Sum('lotFee'), lots=Count('id')).order_by('-total')
    rows = [{'auctionName': r['auctionName'] or '—', 'lots': r['lots'], 'amount': str(r['total'])} for r in agg]
    total = sum((Decimal(r['amount']) for r in rows), Decimal('0.00'))
    columns = [{'key': 'auctionName', 'label': 'Auction'}, {'key': 'lots', 'label': 'Lots'}, {'key': 'amount', 'label': 'Revenue'}]
    return 'Revenue by auction', label, columns, rows, total


def run_by_client(filters):
    qs, label = _revenue_qs(filters)
    agg = qs.values('invoice__winner__companyName', 'invoice__winner__bidderName').annotate(total=Sum('lotFee'), lots=Count('id')).order_by('-total')
    rows = []
    for r in agg:
        name = r['invoice__winner__companyName'] or r['invoice__winner__bidderName']
        rows.append({'client': name, 'lots': r['lots'], 'amount': str(r['total'])})
    total = sum((Decimal(r['amount']) for r in rows), Decimal('0.00'))
    columns = [{'key': 'client', 'label': 'Client'}, {'key': 'lots', 'label': 'Lots'}, {'key': 'amount', 'label': 'Revenue'}]
    return 'Revenue by client', label, columns, rows, total


REPORT_RUNNERS = {
    'outstanding': run_outstanding,
    'overdue': run_overdue,
    'daily': run_daily_collections,
    'monthly': run_monthly_collections,
    'verification': run_verification,
    'by-auction': run_by_auction,
    'by-client': run_by_client,
}


def run_report(report_type, filters):
    runner = REPORT_RUNNERS.get(report_type)
    if not runner:
        raise ValueError(f"Unknown report type: {report_type}")
    return runner(filters)