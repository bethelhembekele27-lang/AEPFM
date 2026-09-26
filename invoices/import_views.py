import csv
import io
import re
from datetime import datetime, date, timedelta
from decimal import Decimal, InvalidOperation

import openpyxl
import xlrd  # legacy .xls only; openpyxl handles .xlsx
from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ImportBatch, Winner, Invoice, InvoiceLot, FeeConfig
from .serializers import ImportBatchSerializer, InvoiceListSerializer
from .permissions import has_permission

from .pagination import StandardPagination


# ---------------------------------------------------------------------------
# Column aliasing — each internal field can be spelled several different
# ways across partner spreadsheets. First alias found in the header row
# wins. Add new aliases here as new naming styles show up; nothing else
# needs to change.
# ---------------------------------------------------------------------------

FIELD_ALIASES = {
    'lotNumber':     ['Lot No', 'Lot Number', 'Lot #', 'LotNo'],
    'auctionName':   ['Auction', 'Auction Name'],
    'winningAmount': ['Amount', 'End Price'],
    'bidderName':    ['Name', 'Winner Name'],
    'winnerPhone':   ['Phone number', 'Winner Phone'],

    # Optional fields below — safe to be absent from a sheet.
    'status':        ['Status', 'Bidder Status'],
    'companyName':   ['Legal Name', 'Company Name'],
    'initialPrice':  ['Initial Price', 'Starting Price'],
    'cpoAmount':     ['CPO Amount'],
    'cpoBank':       ['CPO Bank'],
    'submittedAt':   ['Submitted At', 'End Date'],
}

# The 5 fields a sheet must be able to supply, one way or another, for an
# import to proceed at all.
REQUIRED_FIELDS = ['lotNumber', 'auctionName', 'winningAmount', 'bidderName', 'winnerPhone']

# Human-readable names used in the "missing column" error — names the
# FIELD, not the specific alias spelling, per spec.
FIELD_LABELS = {
    'lotNumber': 'Lot Number',
    'auctionName': 'Auction',
    'winningAmount': 'Amount',
    'bidderName': 'Bidder Name',
    'winnerPhone': 'Phone',
}


def _normalize_header(value):
    """
    Some spreadsheet templates have line breaks (Alt+Enter) or irregular
    whitespace baked into header cells, e.g. 'Lot\nNumber' instead of
    'Lot Number'. Collapse any whitespace run (including newlines) into
    a single space and strip the ends, so header matching isn't broken
    by formatting quirks in the source file.
    """
    if value is None:
        return ''
    return re.sub(r'\s+', ' ', str(value)).strip()


def _resolve_columns(header_row):
    """
    header_row: list of normalized header strings (whitespace collapsed,
    original case preserved).

    Matches each field's alias list against the header row case-
    insensitively. Returns (col_index_by_field, missing_required_fields).
    col_index_by_field maps field_key -> column index, or None if that
    field (only meaningful for optional fields) wasn't found at all.
    """
    normalized_lookup = {}
    for i, h in enumerate(header_row):
        if h:
            key = h.strip().lower()
            # First occurrence wins if a header name repeats.
            normalized_lookup.setdefault(key, i)

    col_index_by_field = {}
    for field, aliases in FIELD_ALIASES.items():
        found_idx = None
        for alias in aliases:
            key = alias.strip().lower()
            if key in normalized_lookup:
                found_idx = normalized_lookup[key]
                break
        col_index_by_field[field] = found_idx

    missing_required = [f for f in REQUIRED_FIELDS if col_index_by_field.get(f) is None]
    return col_index_by_field, missing_required


def _build_column_mapping(col_index_by_field, header_row):
    """
    Snapshot of which ORIGINAL header name (as it actually appeared in
    this file) supplied each known field, e.g. {'lotNumber': 'Lot No',
    'companyName': None, ...}. This is what gets saved onto ImportBatch
    at confirm time, and later shown on the invoice detail view for
    traceability back to the source spreadsheet.
    """
    mapping = {}
    for field, idx in col_index_by_field.items():
        mapping[field] = header_row[idx] if idx is not None else None
    return mapping


def _get_cell(row, col_index_by_field, field, default=None):
    idx = col_index_by_field.get(field)
    if idx is None or idx >= len(row):
        return default
    return row[idx]


def parse_submitted_at(raw):
    """
    Some sheets store this as a string like 'Nov. 20, 2025, 1:13 p.m.'.
    Others (e.g. an 'End Date' column) come back from openpyxl as an
    actual datetime.date/datetime.datetime object. Handle both.
    """
    if raw in (None, ''):
        return None

    if isinstance(raw, datetime):
        dt = raw
    elif isinstance(raw, date):
        dt = datetime(raw.year, raw.month, raw.day)
    else:
        text = str(raw).strip()
        text = re.sub(r'^([A-Za-z]{3})\.', r'\1', text)
        text = re.sub(r'([ap])\.m\.$', lambda m: m.group(1).upper() + 'M',
                      text, flags=re.IGNORECASE)
        try:
            dt = datetime.strptime(text, '%b %d, %Y, %I:%M %p')
        except ValueError:
            return None

    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    return dt


def to_decimal(value):
    if value in (None, ''):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _jsonable(value):
    """
    Extra columns can contain anything openpyxl hands back — datetimes,
    Decimals, etc. — none of which are JSON-serializable as-is. Normalize
    everything to a plain string (or None) for extraFields, since it's
    display-only anyway.
    """
    if value is None:
        return None
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def _read_rows_any_format(file_obj, filename):
    """
    Returns a list of rows (each a list of cell values), first row = header.
    Dispatches on file extension rather than sniffing content: the frontend
    restricts the file picker, so the extension is a reliable signal and we
    avoid reading every upload twice.

    .xls date cells are converted to real datetimes here (xlrd otherwise
    returns raw Excel serial numbers), so both .xls and .xlsx produce the
    same shape for parse_submitted_at downstream.
    """
    name = (filename or '').lower()

    if name.endswith('.csv'):
        text = file_obj.read()
        if isinstance(text, bytes):
            text = text.decode('utf-8-sig')  # strips Excel's UTF-8 BOM on CSV export
        return list(csv.reader(io.StringIO(text)))

    if name.endswith('.xls'):
        book = xlrd.open_workbook(file_contents=file_obj.read())
        sheet = book.sheet_by_index(0)
        rows = []
        for r in range(sheet.nrows):
            row = []
            for c in range(sheet.ncols):
                value = sheet.cell_value(r, c)
                if sheet.cell_type(r, c) == xlrd.XL_CELL_DATE:
                    # xlrd hands back a raw Excel serial number (e.g. 45678.0)
                    # for date cells. Convert to a real datetime so this path
                    # matches what openpyxl returns natively for .xlsx.
                    value = datetime(*xlrd.xldate_as_tuple(value, book.datemode))
                row.append(value)
            rows.append(row)
        return rows

    # default: .xlsx
    wb = openpyxl.load_workbook(file_obj, data_only=True)
    sheet = wb.active
    return [[cell.value for cell in row] for row in sheet.iter_rows()]


def parse_bid_report(file_obj, filename=''):
    """
    Reads the header row, resolves each of the required/optional fields
    to whichever column actually carries it (via FIELD_ALIASES), and
    returns normalized rows. Any header column that isn't claimed by a
    known field is preserved per-row in extraFields, under its original
    column name, so nothing from the sheet is silently dropped.

    Also returns a column_mapping dict — {field_key: original_header_name
    or None} — a snapshot of which real header supplied each field in
    THIS file, for traceability. Callers persist this onto ImportBatch
    at confirm time.

    Winner-row detection: if a status-like column is present and has more
    than one distinct non-empty value in the sheet, a row is a winner
    when that value contains "winner" (case-insensitive). Otherwise
    (no status column, or a constant status column), a row is a winner
    simply if it has a non-empty bidder name.

    Returns (rows, column_mapping, error_message). On error, rows and
    column_mapping are both None.
    """
    all_rows = _read_rows_any_format(file_obj, filename)
    if not all_rows:
        return None, None, "The file is empty."

    raw_header_row = all_rows[0]
    header_row = [_normalize_header(h) for h in raw_header_row]

    col_index_by_field, missing_required = _resolve_columns(header_row)
    if missing_required:
        missing_labels = [FIELD_LABELS[f] for f in missing_required]
        return None, None, f"Missing required column(s): {', '.join(missing_labels)}"

    column_mapping = _build_column_mapping(col_index_by_field, header_row)

    claimed_indices = {idx for idx in col_index_by_field.values() if idx is not None}
    extra_columns = {
        header_row[i]: i
        for i in range(len(header_row))
        if i not in claimed_indices and header_row[i]
    }

    rows = []
    for row_number, row in enumerate(all_rows[1:], start=2):
        bidder_name = _get_cell(row, col_index_by_field, 'bidderName')
        phone = _get_cell(row, col_index_by_field, 'winnerPhone')

        bidder_blank = bidder_name is None or str(bidder_name).strip() == ''
        phone_blank = phone is None or str(phone).strip() == ''
        if bidder_blank and phone_blank:
            continue  # skip fully blank trailing rows

        extra_fields = {
            name: _jsonable(row[idx]) if idx < len(row) else None
            for name, idx in extra_columns.items()
            if idx < len(row) and row[idx] not in (None, '')
        }

        rows.append({
            'rowNumber': row_number,
            'lotNumber': _get_cell(row, col_index_by_field, 'lotNumber'),
            'auctionName': _get_cell(row, col_index_by_field, 'auctionName'),
            'initialPrice': _get_cell(row, col_index_by_field, 'initialPrice'),
            'bidderName': bidder_name,
            'companyName': _get_cell(row, col_index_by_field, 'companyName') or '',
            'winnerPhone': phone,
            'winningAmount': _get_cell(row, col_index_by_field, 'winningAmount'),
            'submittedAt': _get_cell(row, col_index_by_field, 'submittedAt'),
            'cpoAmount': _get_cell(row, col_index_by_field, 'cpoAmount'),
            'cpoBank': _get_cell(row, col_index_by_field, 'cpoBank') or '',
            '_status': _get_cell(row, col_index_by_field, 'status'),
            'extraFields': extra_fields,
        })

    # Decide winner-detection mode once, based on the whole sheet.
    distinct_statuses = {
        str(r['_status']).strip()
        for r in rows
        if r['_status'] not in (None, '') and str(r['_status']).strip() != ''
    }
    use_status_filter = len(distinct_statuses) > 1

    for r in rows:
        if use_status_filter:
            v = r['_status']
            r['isWinner'] = bool(v) and 'winner' in str(v).strip().lower()
        else:
            r['isWinner'] = bool(r['bidderName'] and str(r['bidderName']).strip())
        del r['_status']

    return rows, column_mapping, None


class ImportBatchPreviewView(APIView):
    parser_classes = [MultiPartParser]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        file_obj = request.FILES.get('file')
        company_name = request.data.get('companyName')
        auction_date = request.data.get('auctionDate')

        if not file_obj:
            return Response({'file': ['This field is required.']}, status=status.HTTP_400_BAD_REQUEST)
        if not company_name or not auction_date:
            return Response({'error': 'companyName and auctionDate are required'}, status=status.HTTP_400_BAD_REQUEST)

        rows, column_mapping, header_error = parse_bid_report(file_obj, file_obj.name)
        if header_error:
            return Response({'error': header_error}, status=status.HTTP_400_BAD_REQUEST)

        default_fee_pct = FeeConfig.get_active_percentage()
        groups = {}
        flagged_rows = []
        valid_lot_count = 0

        for row in rows:
            if not row.get('isWinner'):
                continue

            issues = []
            phone = row['winnerPhone']
            phone = str(int(phone)) if isinstance(phone, float) else (str(phone).strip() if phone else '')
            name = (row['bidderName'] or '').strip()
            amount = to_decimal(row['winningAmount'])

            if not name:
                issues.append('missing bidder name')
            if not phone:
                issues.append('missing phone number')
            if amount is None:
                issues.append('missing or invalid winning amount')

            if issues:
                flagged_rows.append({'rowNumber': row['rowNumber'], 'data': row, 'issues': issues})
                continue

            lot_fee = (amount * default_fee_pct / Decimal('100')).quantize(Decimal('0.01'))
            lot = {
                'lotNumber': row['lotNumber'] or '',
                'auctionName': row['auctionName'] or '',
                'initialPrice': str(to_decimal(row['initialPrice']) or ''),
                'winningAmount': str(amount),
                'cpoAmount': str(to_decimal(row['cpoAmount']) or ''),
                'cpoBank': row['cpoBank'] or '',
                'feePercentage': str(default_fee_pct),
                'lotFee': str(lot_fee),
                'submittedAt': row['submittedAt'].isoformat() if hasattr(row['submittedAt'], 'isoformat') else row['submittedAt'],
                'extraFields': row.get('extraFields', {}),
            }

            if phone not in groups:
                groups[phone] = {
                    'bidderName': name,
                    'winnerPhone': phone,
                    'companyName': row.get('companyName') or '',
                    'feePercentage': str(default_fee_pct),
                    'lots': [],
                }
            groups[phone]['lots'].append(lot)
            valid_lot_count += 1

        for group in groups.values():
            group['totalFee'] = str(sum(Decimal(l['lotFee']) for l in group['lots']))

        return Response({
            'groupedWinners': list(groups.values()),
            'flaggedRows': flagged_rows,
            'totalWinners': len(groups),
            'totalLots': valid_lot_count,
            'flaggedCount': len(flagged_rows),
            'columnMapping': column_mapping,
        })


class ImportBatchConfirmView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not has_permission(request.user, 'generate_invoice'):
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

        file_name = request.data.get('fileName', '')
        company_name = request.data.get('companyName')
        auction_date = request.data.get('auctionDate')
        batch_name = request.data.get('batchName', '')
        grouped_winners = request.data.get('groupedWinners', [])
        invalid_records = int(request.data.get('invalidRecords', 0) or 0)
        due_date_input = request.data.get('dueDate')
        due_in_days = int(request.data.get('dueInDays', 14))
        invoice_due_date = due_date_input or (timezone.localdate() + timedelta(days=due_in_days))

        column_mapping = request.data.get('columnMapping')
        if not isinstance(column_mapping, dict):
            column_mapping = {}

        if not company_name or not auction_date:
            return Response({'error': 'companyName and auctionDate are required'}, status=status.HTTP_400_BAD_REQUEST)
        if not grouped_winners:
            return Response({'error': 'groupedWinners must contain at least one winner'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            total_lots = sum(len(g['lots']) for g in grouped_winners)
            batch = ImportBatch.objects.create(
                fileName=file_name,
                batchName=batch_name,
                companyName=company_name,
                auctionDate=auction_date,
                status='confirmed',
                totalRecords=total_lots + invalid_records,
                validRecords=total_lots,
                invalidRecords=invalid_records,
                importedBy=request.user,
                columnMapping=column_mapping,
            )

            created_invoice_ids = []
            for group in grouped_winners:
                lots = group['lots']
                total_winning = sum(Decimal(l['winningAmount']) for l in lots)
                total_cpo = sum((Decimal(l['cpoAmount']) if l.get('cpoAmount') else Decimal('0')) for l in lots)
                total_initial = sum((Decimal(l['initialPrice']) if l.get('initialPrice') else Decimal('0')) for l in lots)
                parsed_submitted_dates = [
                    d for d in (parse_submitted_at(l.get('submittedAt')) for l in lots)
                    if d is not None
                ]
                earliest_submitted = min(parsed_submitted_dates, default=None)

                winner = Winner.objects.create(
                    bidderName=group['bidderName'],
                    winnerPhone=group['winnerPhone'],
                    companyName=group.get('companyName', ''),
                    winningAmount=total_winning,
                    cpoAmount=total_cpo or None,
                    initialPrice=total_initial or None,
                    submittedAt=earliest_submitted,
                    importBatch=batch,
                )

                invoice = Invoice.objects.create(
                    winner=winner,
                    importBatch=batch,
                    invoiceNumber=self._next_invoice_number(),
                    invoiceDate=timezone.localdate(),
                    dueDate=invoice_due_date,
                    status='invoice_generated',
                )

                for lot in lots:
                    raw_initial = lot.get('initialPrice')
                    raw_cpo = lot.get('cpoAmount')
                    raw_fee_pct = group.get('feePercentage', lot.get('feePercentage'))
                    InvoiceLot.objects.create(
                        invoice=invoice,
                        lotNumber=lot['lotNumber'],
                        auctionName=lot['auctionName'],
                        initialPrice=Decimal(raw_initial) if raw_initial else None,
                        winningAmount=Decimal(lot['winningAmount']),
                        cpoAmount=Decimal(raw_cpo) if raw_cpo else None,
                        cpoBank=lot.get('cpoBank', ''),
                        feePercentage=Decimal(raw_fee_pct),
                        submittedAt=parse_submitted_at(lot.get('submittedAt')),
                        extraFields=lot.get('extraFields') or {},
                    )
                created_invoice_ids.append(invoice.id)

        return Response({
            'importBatch': ImportBatchSerializer(batch).data,
            'invoiceIds': created_invoice_ids,
        }, status=status.HTTP_201_CREATED)

    @staticmethod
    def _next_invoice_number():
        year = timezone.localdate().year
        prefix = f'INV-{year}-'
        existing = Invoice.objects.filter(invoiceNumber__startswith=prefix).values_list('invoiceNumber', flat=True)
        nums = [int(n.rsplit('-', 1)[1]) for n in existing if n.rsplit('-', 1)[1].isdigit()]
        return f'{prefix}{(max(nums) + 1 if nums else 1):03d}'


class ImportBatchViewSet(mixins.DestroyModelMixin, viewsets.ReadOnlyModelViewSet):
    queryset = ImportBatch.objects.select_related('importedBy').order_by('-uploadDate')
    serializer_class = ImportBatchSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination

    @action(detail=True, methods=['get'])
    def invoices(self, request, pk=None):
        batch = self.get_object()
        qs = Invoice.objects.select_related('winner').filter(importBatch=batch)
        page = self.paginate_queryset(qs)
        serializer = InvoiceListSerializer(page if page is not None else qs, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def perform_destroy(self, instance):
        if not has_permission(self.request.user, 'delete_records'):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Only administrators can delete import batches.')
        with transaction.atomic():
            Invoice.objects.filter(importBatch=instance).delete()
            Winner.objects.filter(importBatch=instance).delete()
            instance.delete()