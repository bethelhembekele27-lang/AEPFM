from decimal import Decimal
from io import BytesIO

from django.core.files.base import ContentFile
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status as http_status

from invoices.models import GeneratedReport
from invoices.services.report_queries import run_report
from invoices.permissions import has_permission

REPORT_TITLES = {
    'outstanding': 'Outstanding processing fees', 'daily': 'Daily collections',
    'monthly': 'Monthly collections', 'verification': 'Payment verification report',
    'overdue': 'Overdue payments report', 'by-auction': 'Revenue by auction',
    'by-client': 'Revenue by client',
}
STATUS_DISPLAY = {
    'invoice_generated': 'Invoice Generated',
    'pending_payment': 'Pending Payment',
    'payment_submitted': 'Payment Submitted',
    'under_verification': 'Under Verification',
    'paid': 'Paid',
    'overdue': 'Overdue',
    'cancelled': 'Cancelled',
    'waived': 'Waived',
    'verified': 'Verified',
    'rejected': 'Rejected',
    'pending': 'Pending',
        }
import base64
import os
from django.conf import settings

def _watermark_data_uri():
    path = os.path.join(settings.BASE_DIR, 'invoices', 'static', 'watermark.png')
    try:
        with open(path, 'rb') as f:
            encoded = base64.b64encode(f.read()).decode('ascii')
        return f"data:image/png;base64,{encoded}"
    except FileNotFoundError:
        return None
    
def _logo_data_uri():
    path = os.path.join(settings.BASE_DIR, 'invoices', 'static', 'logo.png')
    try:
        with open(path, 'rb') as f:
            encoded = base64.b64encode(f.read()).decode('ascii')
        return f"data:image/png;base64,{encoded}"
    except FileNotFoundError:
        return None

def _parse_filters(data):
    """Filters arrive as querystring-ish flat data from either GET params
    or a POST body — paymentStatus can be a repeated field (list) or a
    single value, normalize either way."""
    payment_status = data.getlist('paymentStatus') if hasattr(data, 'getlist') else data.get('paymentStatus')
    if payment_status and not isinstance(payment_status, list):
        payment_status = [payment_status]
    return {
        'period': data.get('period', 'month'),
        'clientCompany': data.get('clientCompany') or None,
        'importBatch': data.get('importBatch') or None,
        'dateFrom': data.get('dateFrom') or None,
        'dateTo': data.get('dateTo') or None,
        'auction': data.get('auction') or None,
        'paymentStatus': payment_status or None,
    }


class ReportPreviewView(APIView):
    """POST /api/reports/preview/ — runs the query, returns JSON only. Saves nothing."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not has_permission(request.user, 'view_reports'):
            return Response({'error': 'You do not have permission to view reports.'}, status=http_status.HTTP_403_FORBIDDEN)
        report_type = request.data.get('reportType')
        if report_type not in REPORT_TITLES:
            return Response({'error': f'Unknown reportType: {report_type}'}, status=http_status.HTTP_400_BAD_REQUEST)

        filters = _parse_filters(request.data)
        try:
            title, period_label, columns, rows, total = run_report(report_type, filters)
        except Exception as e:
            return Response({'error': str(e)}, status=http_status.HTTP_400_BAD_REQUEST)

        return Response({
            'reportType': report_type, 'title': title, 'periodLabel': period_label,
            'columns': columns, 'rows': rows, 'count': len(rows), 'total': str(total),
        })


import logging
logger = logging.getLogger(__name__)

class ReportGeneratePdfView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not has_permission(request.user, 'view_reports'):
            return Response({'error': 'You do not have permission to generate reports.'}, status=http_status.HTTP_403_FORBIDDEN)
        report_type = request.data.get('reportType')
        if report_type not in REPORT_TITLES:
            return Response({'error': f'Unknown reportType: {report_type}'}, status=http_status.HTTP_400_BAD_REQUEST)

        filters = _parse_filters(request.data)
        try:
            title, period_label, columns, rows, total = run_report(report_type, filters)
        except Exception as e:
            logger.exception("run_report failed")
            return Response({'error': str(e)}, status=http_status.HTTP_400_BAD_REQUEST)

        try:
            from weasyprint import HTML
            html_string = self._render_report_html(title, period_label, columns, rows, total)
            pdf_bytes = HTML(string=html_string).write_pdf()

            from django.utils import timezone
            report = GeneratedReport(
                reportType=report_type, title=title, periodLabel=period_label,
                filters=filters, rowCount=len(rows), totalAmount=total,
                generatedBy=request.user if request.user.is_authenticated else None,
            )
            fname = f"{report_type}-{timezone.now():%Y%m%d%H%M%S}.pdf"
            report.file.save(fname, ContentFile(pdf_bytes), save=False)
            report.save()

            from django.http import FileResponse
            return FileResponse(BytesIO(pdf_bytes), as_attachment=True,
                                 filename=f"{title.replace(' ', '_')}.pdf", content_type='application/pdf')
        except Exception as e:
            logger.exception("PDF generation/save failed")
            return Response({'error': f'PDF generation failed: {e}'}, status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)

    

    @staticmethod
    def _render_report_html(title, period_label, columns, rows, total):
        head = ''.join(f"<th>{c['label']}</th>" for c in columns)

        def fmt_cell(row, col):
            key = col['key']
            val = row.get(key, '')
            if key in ('status', 'result') and val in STATUS_DISPLAY:
                return STATUS_DISPLAY[val]
            if key == 'amount':
                try:
                    return f"ETB {Decimal(val):,.2f}"
                except Exception:
                    return val
            return val

        body = ''.join(
            '<tr>' + ''.join(f"<td>{fmt_cell(r, c)}</td>" for c in columns) + '</tr>'
            for r in rows
        )

        watermark_uri = _watermark_data_uri()
        watermark_html = f'<img class="watermark" src="{watermark_uri}">' if watermark_uri else ''

        logo_uri = _logo_data_uri()
        logo_html = f'<img class="logo" src="{logo_uri}">' if logo_uri else ''

        return f"""
        <!DOCTYPE html><html><head><meta charset="UTF-8"><style>
            @page {{ size: A4; margin: 30px; }}
            body {{ font-family: sans-serif; font-size: 12px; color: #1B1D1F; }}
            .watermark {{
                position: fixed;
                left: 25%;
                top: 50%;
                transform: translate(-50%, -25%);
                opacity: 0.3;
                z-index: -1;
                width: 900px;
            }}
            .header-row {{ margin-bottom: 10px; }}
            .logo {{ height: 42px; width: auto; display: block; margin-bottom: 6px; }}
            .brand {{ font-size: 13px; font-weight: 600; color: #63675F; text-transform: uppercase; letter-spacing: 0.04em; }}
            .header-bar {{ background: #AD7F27; height: 6px; width: 100%; margin-bottom: 18px; }}
            h1 {{ font-size: 20px; margin: 0 0 2px; color: #14171C; }}
            .meta {{ color: #63675F; margin-bottom: 18px; font-size: 12px; }}
            table {{ width: 100%; border-collapse: collapse; }}
            th {{ text-align: left; padding: 8px 10px; border-bottom: 2px solid #AD7F27; background: #F4EBD6; color: #1B1D1F; font-size: 11px; text-transform: uppercase; letter-spacing: 0.03em; }}
            td {{ text-align: left; padding: 7px 10px; border-bottom: 1px solid #DEE0DA; color: #1B1D1F; }}
            tr:nth-child(even) td {{ background: #F9F9F7; }}
            .total {{ margin-top: 14px; font-weight: bold; text-align: right; font-size: 13px; color: #14171C; }}
        </style></head><body>
            {watermark_html}
            <div class="header-row">
                {logo_html}
                <div class="brand">Auction Ethiopia — Processing Fee Management</div>
            </div>
            <div class="header-bar"></div>
            <h1>{title}</h1>
            <div class="meta">{period_label} &middot; {len(rows)} record(s)</div>
            <table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>
            <div class="total">Total: ETB {total:,.2f}</div>
        </body></html>
        """

class FilterOptionsView(APIView):
    """GET /api/reports/filter-options/ — populates the Client/Company and
    Import Batch dropdowns with real values pulled from actual invoices,
    instead of making users guess/type them freehand."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from invoices.models import Winner, ImportBatch, Invoice

        companies = (
            Winner.objects.filter(invoices__isnull=False)
            .exclude(companyName='')
            .values_list('companyName', flat=True)
            .distinct()
            .order_by('companyName')
        )

        batches = (
            ImportBatch.objects.filter(invoices__isnull=False)
            .distinct()
            .order_by('-uploadDate')
        )

        return Response({
            'companies': list(companies),
            'importBatches': [
                {'id': b.id, 'label': b.batchName or b.fileName}
                for b in batches
            ],
            'paymentStatuses': [{'value': v, 'label': l} for v, l in Invoice.STATUS_CHOICES],
        })
class RecentReportsView(APIView):
    """GET /api/reports/recent/ — backs the 'Recently generated' list."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        reports = GeneratedReport.objects.order_by('-generatedAt')[:20]
        return Response([{
            'id': r.id, 'reportType': r.reportType, 'title': r.title, 'periodLabel': r.periodLabel,
            'rowCount': r.rowCount, 'totalAmount': str(r.totalAmount) if r.totalAmount is not None else None,
            'generatedAt': r.generatedAt.isoformat(),
            'generatedBy': (r.generatedBy.get_full_name() or r.generatedBy.get_username()) if r.generatedBy else '—',
            'fileUrl': r.file.url if r.file else None,
        } for r in reports])