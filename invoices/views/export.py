"""
Read-only export API for a companion CRM to pull verified, paid winners.

Auth is a dedicated ServiceApiKey (Bearer token), never a staff token —
deliberately a separate trust boundary from the rest of the app, so it can
be revoked independently without touching any human account.

Never raises into a 500 for a malformed request: every failure is a clear
{"error": "..."} response, matching the rest of this codebase's contract.
"""
import base64
import hashlib
import hmac
import json

from django.db.models import Q
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from invoices.audit import log_system_audit
from invoices.models import Payment, ServiceApiKey

MAX_LIMIT = 100


class ExportApiThrottle(SimpleRateThrottle):
    """Keyed on the presented key (hashed), not IP — so one client's traffic
    can't be lumped in with another's, and an unauthenticated flood doesn't
    share a bucket with a legitimate caller. The presented value is hashed
    before it becomes a cache key, so no raw secret ends up in the throttle
    backend."""

    scope = 'export_verified_winners'

    def get_cache_key(self, request, view):
        auth = request.headers.get('Authorization', '')
        token = auth[7:].strip() if auth.startswith('Bearer ') else self.get_ident(request)
        ident = hashlib.sha256(token.encode()).hexdigest()[:16]
        return self.cache_format % {'scope': self.scope, 'ident': ident}


def _authenticate(request):
    """Returns (ServiceApiKey, None) or (None, error_string). Never raises.

    Compares with hmac.compare_digest against each active key's hash rather
    than a plain == so the comparison time doesn't leak how much of a
    guessed hash matched.
    """
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return None, 'Missing or invalid Authorization header.'
    raw = auth[7:].strip()
    if not raw:
        return None, 'Missing API key.'
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    for key in ServiceApiKey.objects.filter(isActive=True):
        if hmac.compare_digest(key.hashedKey, hashed):
            return key, None
    return None, 'Invalid or inactive API key.'


def _encode_cursor(dt, invoice_number):
    payload = json.dumps([dt.isoformat(), invoice_number])
    return base64.urlsafe_b64encode(payload.encode()).decode()


def _decode_cursor(raw):
    """Returns (datetime, invoice_number) or None. Never raises on garbage."""
    try:
        dt_str, inv = json.loads(base64.urlsafe_b64decode(raw.encode()).decode())
        dt = parse_datetime(dt_str)
        if dt is None:
            return None
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt)
        return dt, inv
    except Exception:
        return None


def _first_present(extra_fields, candidate_keys):
    """Best-effort lookup across a few likely spreadsheet-column names.

    extraFields has NO fixed schema — it holds whatever columns a given
    import batch happened to carry that didn't match a known field alias,
    so it varies per upload. These keys are not guaranteed to exist; this
    only checks the common ones when they do.
    """
    for k in candidate_keys:
        v = extra_fields.get(k)
        if v:
            return str(v)
    return None


def _verified_winners_queryset(since_dt, cursor_dt, cursor_inv):
    """
    'Verified' = the Payment that actually got this invoice approved —
    verificationStatus='manager_approved', which is set identically whether
    a human approved it or Verify.ET automation did, so both paths export
    the same way. Scoped to invoices currently 'paid'.

    Ordered by (verifiedAt, invoiceNumber) for stable keyset pagination —
    offset pagination would skip or repeat rows if an invoice were approved
    mid-pagination.

    KNOWN LIMITATION: nothing in the schema prevents an invoice from having
    more than one manager_approved Payment (e.g. after a manual status
    correction). Each would appear as its own row here; the view dedupes by
    invoice within a page, keeping the first. Flagged rather than silently
    hidden.
    """
    qs = (
        Payment.objects
        .filter(invoice__status='paid', verificationStatus='manager_approved')
        .annotate(exportVerifiedAt=Coalesce('managerVerifiedDate', 'verifiedDate', 'invoice__updatedAt'))
        .select_related('invoice', 'invoice__winner')
        .prefetch_related('invoice__lots')
        .order_by('exportVerifiedAt', 'invoice__invoiceNumber')
    )
    if since_dt:
        qs = qs.filter(exportVerifiedAt__gte=since_dt)
    if cursor_dt is not None:
        qs = qs.filter(
            Q(exportVerifiedAt__gt=cursor_dt)
            | Q(exportVerifiedAt=cursor_dt, invoice__invoiceNumber__gt=cursor_inv)
        )
    return qs


def _serialize(payment):
    inv = payment.invoice
    winner = inv.winner
    check = getattr(payment, 'verifyEtCheck', None)
    amount_paid = check.amount if (check is not None and check.amount is not None) else payment.amountPaid

    lots, auction_name = [], ''
    for lot in inv.lots.all():
        extra = lot.extraFields or {}
        if not auction_name:
            auction_name = lot.auctionName or ''
        lots.append({
            'lotNumber': lot.lotNumber or '',
            'description': _first_present(extra, ['Item Description', 'Description', 'Item', 'ItemName']) or '',
            'winningAmount': str(lot.winningAmount) if lot.winningAmount is not None else '',
            'quantity': _first_present(extra, ['Quantity', 'Qty']) or '',
            'location': _first_present(extra, ['Location', 'Pickup Location', 'Warehouse']) or '',
        })

    return {
        'invoiceNumber': inv.invoiceNumber or '',
        'bidderName': winner.bidderName or '',
        'bidderNameAmharic': winner.bidderNameAmharic or '',
        'companyName': winner.companyName or '',
        'phone': winner.winnerPhone or '',
        'email': winner.winnerEmail or '',
        'auctionName': auction_name,
        'lots': lots,
        'amountPaid': str(amount_paid) if amount_paid is not None else '',
        'verifiedAt': payment.exportVerifiedAt.isoformat() if payment.exportVerifiedAt else '',
    }


class VerifiedWinnersExportView(APIView):
    """GET /api/export/v1/verified-winners/?since=<ISO>&cursor=<opaque>&limit=100"""

    permission_classes = [AllowAny]  # auth is the service key, not staff tokens
    throttle_classes = [ExportApiThrottle]

    def get(self, request):
        key, err = _authenticate(request)
        if err:
            return Response({'error': err}, status=401)

        try:
            limit = min(max(int(request.query_params.get('limit', 100)), 1), MAX_LIMIT)
        except (TypeError, ValueError):
            return Response({'error': 'limit must be an integer.'}, status=400)

        since_raw = request.query_params.get('since')
        since_dt = None
        if since_raw:
            # In a query string '+' decodes to a space, so an ISO timestamp
            # with a +00:00 offset arrives as "... 00:00" and fails to parse.
            # Put it back so clients that don't percent-encode still work.
            since_dt = parse_datetime(since_raw.replace(' ', '+'))
            if since_dt is None:
                return Response({'error': 'since must be a valid ISO 8601 datetime.'}, status=400)
            if timezone.is_naive(since_dt):
                since_dt = timezone.make_aware(since_dt)

        cursor_raw = request.query_params.get('cursor')
        cursor_dt, cursor_inv = None, None
        if cursor_raw:
            decoded = _decode_cursor(cursor_raw)
            if decoded is None:
                return Response({'error': 'cursor is invalid or expired.'}, status=400)
            cursor_dt, cursor_inv = decoded

        qs = _verified_winners_queryset(since_dt, cursor_dt, cursor_inv)
        page = list(qs[:limit + 1])   # one extra row tells us if there's a next page
        has_more = len(page) > limit
        page = page[:limit]

        results, seen = [], set()
        for payment in page:
            if payment.invoice_id in seen:
                continue
            seen.add(payment.invoice_id)
            results.append(_serialize(payment))

        next_cursor = None
        if has_more and page:
            last = page[-1]
            next_cursor = _encode_cursor(last.exportVerifiedAt, last.invoice.invoiceNumber)

        key.lastUsedAt = timezone.now()
        key.save(update_fields=['lastUsedAt'])
        log_system_audit(
            None, 'Export API call', target=key.name,
            details=f'returned {len(results)} result(s); since={since_raw or "none"}; '
                    f'cursor={"yes" if cursor_raw else "no"}',
        )

        return Response({
            'version': 1,
            'generatedAt': timezone.now().isoformat(),
            'nextCursor': next_cursor,
            'results': results,
        })
