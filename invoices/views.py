from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.http import FileResponse
from rest_framework import viewsets, generics, status
from rest_framework.decorators import action
from rest_framework.response import Response    
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.pagination import PageNumberPagination
from .pagination import StandardPagination
from io import BytesIO
from decimal import Decimal

from .audit import log_audit
from .pdf_rendering import load_invoice_images, render_invoice_html
import base64
import os
from django.conf import settings

from .models import (
    Auction, Winner, Invoice, InvoiceLot, Payment, Attachment, FeeConfig, AuditLog,OfficeSettings,
)
from .serializers import (
    AuctionSerializer, WinnerSerializer, InvoiceListSerializer,
    InvoiceDetailSerializer, PaymentSerializer, AttachmentSerializer,
    AuditLogSerializer, FeeConfigSerializer, LoginSerializer, GoogleLoginSerializer,
    _login_result, OfficeSettingsSerializer,
)
from .permissions import ReadOnlyForViewer, ActionPermissionMap, can_transition, has_permission

from datetime import datetime, timedelta, date

class AuctionViewSet(viewsets.ModelViewSet):
    queryset = Auction.objects.all().order_by('-auctionDate')
    serializer_class = AuctionSerializer
    permission_classes = [IsAuthenticated, ReadOnlyForViewer]
    pagination_class = StandardPagination


class WinnerViewSet(viewsets.ModelViewSet):
    queryset = Winner.objects.select_related('auction', 'importBatch').order_by('-createdAt')
    serializer_class = WinnerSerializer
    permission_classes = [IsAuthenticated, ReadOnlyForViewer, ActionPermissionMap]
    pagination_class = StandardPagination
    action_permissions = {
        'update': 'edit_invoice',
        'partial_update': 'edit_invoice',
    }


class InvoiceViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, ReadOnlyForViewer, ActionPermissionMap]
    pagination_class = StandardPagination
    action_permissions = {
        'destroy': 'delete_records',
        'update': 'edit_invoice',
        'partial_update': 'edit_invoice',
        'generate_pdf': 'generate_invoice',
        'change_status': 'change_status_generic',
        'extend_due_date': 'extend_due_date',
    }

    def get_queryset(self):
        qs = Invoice.objects.select_related('winner').order_by('-createdAt')
        p = self.request.query_params

        if p.get('status'):
            qs = qs.filter(status=p['status'])
        if p.get('batchId'):
            qs = qs.filter(importBatch_id=p['batchId'])
        if p.get('bidderName'):
            qs = qs.filter(winner__bidderName__icontains=p['bidderName'])
        if p.get('phoneNumber'):
            qs = qs.filter(winner__winnerPhone__icontains=p['phoneNumber'])
        if p.get('auctionCompany'):
            qs = qs.filter(importBatch__companyName__icontains=p['auctionCompany'])
        if p.get('lotNo'):
            qs = qs.filter(lots__lotNumber__icontains=p['lotNo']).distinct()
        if p.get('dateFrom'):
            qs = qs.filter(dueDate__gte=p['dateFrom'])
        if p.get('dateTo'):
            qs = qs.filter(dueDate__lte=p['dateTo'])

        # Finance-only (verify_payment without the fuller Operations privileges)
        # sees only Paid invoices — matches the requirement that unverified
        # invoices should not appear for them at all, not just be filterable out.
        if has_permission(self.request.user, 'verify_payment') and not has_permission(self.request.user, 'change_status_generic'):
            qs = qs.filter(status='paid')

        return qs

    def get_serializer_class(self):
        return InvoiceListSerializer if self.action == 'list' else InvoiceDetailSerializer

    def retrieve(self, request, *args, **kwargs):
        instance = get_object_or_404(
            Invoice.objects.select_related('winner').prefetch_related('lots', 'payments', 'attachments'),
            pk=kwargs['pk'],
        )
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    

    @action(detail=False, methods=['get'])
    def summary(self, request):
        if not has_permission(request.user, 'view_dashboard'):
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

        today = timezone.localdate()
        month_start = today.replace(day=1)
        week_start = today - timedelta(days=today.weekday())

        status_keys = [
            'invoice_generated', 'pending_payment', 'payment_submitted',
            'under_verification', 'paid', 'overdue', 'cancelled', 'waived',
        ]
        counts = {k: 0 for k in status_keys}
        for row in Invoice.objects.values('status').annotate(n=Count('id')):
            counts[row['status']] = row['n']

        # --- Ground truth is Invoice.status, not Payment rows ---
        paid_lots = InvoiceLot.objects.filter(invoice__status='paid')
        total_collected = paid_lots.aggregate(t=Sum('lotFee'))['t'] or 0
        paid_auction_count = paid_lots.exclude(auctionName='').values('auctionName').distinct().count()

        total_due = InvoiceLot.objects.aggregate(t=Sum('lotFee'))['t'] or 0

        unpaid_statuses = ['invoice_generated', 'pending_payment', 'payment_submitted', 'under_verification', 'overdue']
        outstanding = (
            InvoiceLot.objects.filter(invoice__status__in=unpaid_statuses)
            .aggregate(t=Sum('lotFee'))['t'] or 0
        )
        outstanding_count = Invoice.objects.filter(status__in=unpaid_statuses).count()

        collection_pct = (total_collected / total_due * 100) if total_due else 0

        def received_since(start_date):
            # Same definition as report_queries._revenue_qs: fees (lotFee) of invoices that are
            # Paid AND have a verified payment dated in the period. Subquery, not a join,
            # so an invoice with two verified payments is never counted twice.
            verified_invoice_ids = Payment.objects.filter(
                paymentStatus='verified',
                verifiedDate__date__gte=start_date,
            ).values('invoice_id')
            return (
                InvoiceLot.objects.filter(invoice__status='paid', invoice_id__in=verified_invoice_ids)
                .aggregate(t=Sum('lotFee'))['t'] or 0
            )
        year_start = today.replace(month=1, day=1)
        today_collected = received_since(today)
        week_collected = received_since(week_start)
        month_collected = received_since(month_start)
        year_collected = received_since(year_start)

        revenue_by_auction = [
            {'auctionName': r['auctionName'], 'total': str(r['total']), 'count': r['count']}
            for r in (
                paid_lots.exclude(auctionName='')
                .values('auctionName')
                .annotate(total=Sum('lotFee'), count=Count('id'))
                .order_by('-total')[:10]
            )
        ]

        revenue_by_client = [
            {
                'clientName': r['invoice__winner__companyName'] or r['invoice__winner__bidderName'],
                'total': str(r['total']),
                'count': r['count'],
            }
            for r in (
                paid_lots.values('invoice__winner__companyName', 'invoice__winner__bidderName')
                .annotate(total=Sum('lotFee'), count=Count('id'))
                .order_by('-total')[:10]
            )
        ]

        return Response({
            'totalInvoices': Invoice.objects.count(),
            'totalAmountDue': str(total_due),
            'totalCollected': str(total_collected),
            'totalOutstanding': str(outstanding),
            'collectionPercentage': f"{collection_pct:.2f}",
            'paidAuctionCount': paid_auction_count,
            'outstandingCount': outstanding_count,
            'invoiceGeneratedCount': counts['invoice_generated'],
            'pendingPaymentCount': counts['pending_payment'],
            'paymentSubmittedCount': counts['payment_submitted'],
            'underVerificationCount': counts['under_verification'],
            'paidCount': counts['paid'],
            'overdueCount': counts['overdue'],
            'cancelledCount': counts['cancelled'],
            'waivedCount': counts['waived'],
            'paymentsReceivedToday': str(today_collected),
            'paymentsReceivedThisWeek': str(week_collected),
            'paymentsReceivedThisMonth': str(month_collected),
            'paymentsReceivedThisYear': str(year_collected),
            'revenueByAuction': revenue_by_auction,
            'revenueByClient': revenue_by_client,
        })

    @action(detail=True, methods=['post'], url_path='generate-pdf')
    def generate_pdf(self, request, pk=None):
        from django.db import transaction
        invoice = self.get_object()

        fee_percentage = request.data.get('feePercentage')
        auction_ref_number = request.data.get('auctionRefNumber', '')
        bidder_name_amharic = request.data.get('bidderNameAmharic', '').strip()
        amount_in_words = request.data.get('amountInWords', '').strip()
        fee_in_words = request.data.get('feeInWords', '').strip()
        office_address = request.data.get('officeAddress', '').strip()
        total_amount_override = request.data.get('totalAmount')
        fee_amount_override = request.data.get('feeAmount')
        bank_account_override = request.data.get('bankAccount', '').strip()
        paragraph1_override = request.data.get('paragraph1', '').strip()
        paragraph2_override = request.data.get('paragraph2', '').strip()

        images = load_invoice_images()

        try:
            from weasyprint import HTML
            with transaction.atomic():
                if fee_percentage is not None:
                    fee_percentage = Decimal(str(fee_percentage))
                    for lot in invoice.lots.all():
                        lot.feePercentage = fee_percentage
                        lot.save()
                if bidder_name_amharic:
                    invoice.winner.bidderNameAmharic = bidder_name_amharic
                    invoice.winner.save(update_fields=['bidderNameAmharic'])

                previous = invoice.status
                if invoice.status == 'invoice_generated':
                    invoice.status = 'pending_payment'
                    invoice.save(update_fields=['status', 'updatedAt'])
                log_audit(invoice, 'Generate invoice PDF', request.user, previous, invoice.status, action_type='generate_invoice_pdf')

                invoice.letterData = {
                    'auctionRefNumber': auction_ref_number,
                    'amountInWords': amount_in_words,
                    'feeInWords': fee_in_words,
                    'officeAddress': office_address,
                    'totalAmount': '' if total_amount_override in (None, '') else str(total_amount_override),
                    'feeAmount': '' if fee_amount_override in (None, '') else str(fee_amount_override),
                    'bankAccount': bank_account_override,
                    'paragraph1': paragraph1_override,
                    'paragraph2': paragraph2_override,
                }
                invoice.save(update_fields=['letterData', 'updatedAt'])

                html_string = render_invoice_html(
                    invoice, auction_ref_number, images,
                    amount_in_words, fee_in_words, office_address,
                    total_amount_override, fee_amount_override, bank_account_override,
                    paragraph1_override, paragraph2_override,
                )
                pdf_bytes = HTML(string=html_string).write_pdf()
        except Exception as e:
            return Response({'detail': f'PDF generation failed: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return FileResponse(
            BytesIO(pdf_bytes),
            as_attachment=True,
            filename=f"Invoice_{invoice.invoiceNumber}.pdf",
            content_type='application/pdf'
        )

    @action(detail=True, methods=['post'], url_path='change-status')
    def change_status(self, request, pk=None):
        invoice = self.get_object()
        new_status = request.data.get('status')
        reason = request.data.get('reason', '')

        if not new_status:
            return Response({'status': ['This field is required.']}, status=status.HTTP_400_BAD_REQUEST)

        if not can_transition(invoice.status, new_status, request.user):
            return Response({'error': 'Status transition not allowed'}, status=status.HTTP_400_BAD_REQUEST)

        previous = invoice.status
        invoice.status = new_status
        invoice.save(update_fields=['status', 'updatedAt'])
        log_audit(invoice, f'Status changed to {new_status}', request.user, previous, new_status, reason, action_type='change_status')
        latest_payment = invoice.payments.order_by('-uploadedAt').first()
        if latest_payment:
            if new_status in ('under_verification', 'paid') and latest_payment.paymentStatus == 'pending':
                latest_payment.paymentStatus = 'verified'
                latest_payment.verifiedBy = request.user
                latest_payment.verifiedDate = timezone.now()
                latest_payment.save()
            elif new_status == 'pending_payment' and previous == 'payment_submitted':
                latest_payment.paymentStatus = 'rejected'
                latest_payment.save()

        invoice.refresh_from_db()
        serializer = InvoiceDetailSerializer(invoice)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='extend-due-date')
    def extend_due_date(self, request, pk=None):
        invoice = self.get_object()
        new_due_date = request.data.get('dueDate')
        if not new_due_date:
            return Response({'dueDate': ['This field is required.']}, status=status.HTTP_400_BAD_REQUEST)

        previous = str(invoice.dueDate)
        invoice.dueDate = new_due_date
        invoice.save(update_fields=['dueDate', 'updatedAt'])
        log_audit(invoice, 'Extend due date', request.user, previous, new_due_date, request.data.get('reason', ''), action_type='extend_due_date')
        serializer = InvoiceDetailSerializer(invoice)
        return Response(serializer.data)

    @action(detail=True, methods=['get', 'post'], url_path='payments')
    def payments(self, request, pk=None):
        invoice = self.get_object()

        if request.method == 'GET':
            serializer = PaymentSerializer(invoice.payments.all().order_by('-uploadedAt'), many=True)
            return Response(serializer.data)

        if not has_permission(request.user, 'upload_payment_proof'):
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

        serializer = PaymentSerializer(data={**request.data, 'invoice': invoice.id})
        serializer.is_valid(raise_exception=True)
        serializer.save()

        if invoice.status == 'pending_payment':
            previous = invoice.status
            invoice.status = 'payment_submitted'
            invoice.save(update_fields=['status', 'updatedAt'])
            log_audit(invoice, 'Payment uploaded', request.user, previous, invoice.status, action_type='upload_payment')
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get', 'post'], url_path='attachments')
    def attachments_action(self, request, pk=None):
        invoice = self.get_object()

        if request.method == 'GET':
            serializer = AttachmentSerializer(invoice.attachments.all().order_by('-uploadDate'), many=True)
            return Response(serializer.data)

        if not has_permission(request.user, 'upload_payment_proof'):
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

        data = request.data.copy()
        data['invoice'] = invoice.id
        serializer = AttachmentSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save(uploadedBy=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AttachmentDeleteView(generics.DestroyAPIView):
    """DELETE /api/attachments/{id}/ — deliberately delete-only, matches the contract."""
    queryset = Attachment.objects.all()
    serializer_class = AttachmentSerializer
    permission_classes = [IsAuthenticated]

    def perform_destroy(self, instance):
        if not has_permission(self.request.user, 'delete_records'):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Permission denied')
        instance.delete()


class PaymentDeleteView(generics.DestroyAPIView):
    """DELETE /api/payments/{id}/ — removes a payment/receipt record entirely."""
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def perform_destroy(self, instance):
        if not has_permission(self.request.user, 'delete_records'):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Only administrators can delete payment records.')
        instance.delete()


class AuditLogListView(generics.ListAPIView):
    """
    Read-only at every layer — the model has no delete/update path exposed
    anywhere, admin.py blocks all writes, and this view is List-only.
    Supports ?user_id=, ?role=, ?action=, ?date_from=, ?date_to=, ?ordering=
    """
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination

    ALLOWED_ORDER_FIELDS = {'actionDate', 'userRole', 'action', 'performedBy__username'}

    def list(self, request, *args, **kwargs):
        if not has_permission(request.user, 'view_audit'):
            return Response({'error': "You don't have permission to view the audit trail."}, status=status.HTTP_403_FORBIDDEN)
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        qs = AuditLog.objects.select_related('invoice', 'performedBy').order_by('-actionDate')
        p = self.request.query_params

        if p.get('invoice_id'):
            qs = qs.filter(invoice_id=p['invoice_id'])
        if p.get('user_id'):
            qs = qs.filter(performedBy_id=p['user_id'])
        if p.get('role'):
            qs = qs.filter(userRole=p['role'])
        if p.get('action'):
            qs = qs.filter(actionType=p['action'])
        if p.get('date_from'):
            qs = qs.filter(actionDate__date__gte=p['date_from'])
        if p.get('date_to'):
            qs = qs.filter(actionDate__date__lte=p['date_to'])

        ordering = p.get('ordering')
        if ordering and ordering.lstrip('-') in self.ALLOWED_ORDER_FIELDS:
            qs = qs.order_by(ordering)

        return qs

class AuditLogFilterOptionsView(APIView):
    """GET /api/audit-logs/filter-options/ — populates the User/Role/Action dropdowns."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not has_permission(request.user, 'view_audit'):
            return Response({'error': "You don't have permission to view the audit trail."}, status=status.HTTP_403_FORBIDDEN)

        user_rows = (
            AuditLog.objects.exclude(performedBy__isnull=True)
            .values_list('performedBy_id', 'performedBy__username')
            .distinct()
            .order_by('performedBy__username')
        )
        roles = (
            AuditLog.objects.exclude(userRole='')
            .values_list('userRole', flat=True)
            .distinct()
            .order_by('userRole')
        )

        return Response({
            'users': [{'id': uid, 'username': uname} for uid, uname in user_rows],
            'roles': list(roles),
            'actionTypes': [{'value': v, 'label': l} for v, l in AuditLog.ACTION_TYPE_CHOICES],
        })
        
class AuditLogClearView(APIView):
    """DELETE /api/audit-logs/clear/ — permanently wipes every audit log entry.
    Administrator-only, backs the 'Clear audit trail' button."""
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        if not has_permission(request.user, 'delete_records'):
            return Response({'error': 'Only administrators can clear the audit trail.'}, status=status.HTTP_403_FORBIDDEN)
        count, _ = AuditLog.objects.all().delete()
        return Response({'deleted': count})
    
class FeeConfigView(generics.GenericAPIView):
    """GET current active config, PUT to create a new active one (keeps history — see FeeConfig docstring)."""
    serializer_class = FeeConfigSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request):
        config = FeeConfig.objects.filter(is_active=True).first()
        if not config:
            return Response({'percentage': '0.95', 'configuredBy': '', 'configuredAt': None})
        return Response(FeeConfigSerializer(config).data)

    def put(self, request):
        if not has_permission(request.user, 'manage_fee_config'):
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        percentage = request.data.get('percentage')
        if percentage is None:
            return Response({'percentage': ['This field is required.']}, status=status.HTTP_400_BAD_REQUEST)

        FeeConfig.objects.filter(is_active=True).update(is_active=False)
        config = FeeConfig.objects.create(percentage=percentage, configured_by=request.user, is_active=True)
        return Response(FeeConfigSerializer(config).data)


# ================================================================= Auth View

class LoginView(APIView):
    """
    POST /api/auth/login/
    Body: {username, password}
    Returns: {token, username, role}
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            result = serializer.create(serializer.validated_data)
            return Response(result, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class GoogleLoginView(APIView):
    """POST /api/auth/google/ {id_token} -> {token, username, role}"""
    permission_classes = [AllowAny]

    def post(self, request):
        if not settings.GOOGLE_CLIENT_ID:
            return Response({'error': 'Google sign-in is not configured on this server.'},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)
        serializer = GoogleLoginSerializer(data=request.data)
        if not serializer.is_valid():
            first = next(iter(serializer.errors.values()))[0]
            return Response({'error': str(first)}, status=status.HTTP_401_UNAUTHORIZED)
        return Response(_login_result(serializer.validated_data['user']))


class OfficeSettingsView(generics.GenericAPIView):
    """GET current saved office address, PUT to save a new one (admin only)."""
    serializer_class = OfficeSettingsSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request):
        config = OfficeSettings.objects.filter(isActive=True).first()
        if not config:
            return Response({'address': '', 'configuredBy': '', 'configuredAt': None})
        return Response(OfficeSettingsSerializer(config).data)

    def put(self, request):
        if not has_permission(request.user, 'manage_fee_config'):  # reuse admin-only key
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        address = request.data.get('address', '')
        OfficeSettings.objects.filter(isActive=True).update(isActive=False)
        config = OfficeSettings.objects.create(address=address, configuredBy=request.user, isActive=True)
        return Response(OfficeSettingsSerializer(config).data)


class ManualWinnerCreateView(APIView):
    """POST /api/winners/manual/ — one winner + invoice + lots, no Excel import."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not has_permission(request.user, 'generate_invoice'):
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

        bidder_name = request.data.get('bidderName', '').strip()
        phone = request.data.get('winnerPhone', '').strip()
        company_name = request.data.get('companyName', '').strip()
        lots = request.data.get('lots', [])
        due_date = request.data.get('dueDate') or (timezone.localdate() + timedelta(days=14))

        if not bidder_name or not phone:
            return Response({'error': 'Bidder name and phone are required.'}, status=status.HTTP_400_BAD_REQUEST)
        if not lots:
            return Response({'error': 'At least one lot is required.'}, status=status.HTTP_400_BAD_REQUEST)

        from django.db import transaction
        default_fee_pct = FeeConfig.get_active_percentage()
        with transaction.atomic():
            winner = Winner.objects.create(
                bidderName=bidder_name, winnerPhone=phone, companyName=company_name,
                winningAmount=sum(Decimal(str(l['winningAmount'])) for l in lots),
            )
            invoice = Invoice.objects.create(
                winner=winner, invoiceNumber=self._next_invoice_number(),
                invoiceDate=timezone.localdate(), dueDate=due_date, status='invoice_generated',
            )
            for lot in lots:
                InvoiceLot.objects.create(
                    invoice=invoice, lotNumber=lot.get('lotNumber', ''), auctionName=lot.get('auctionName', ''),
                    winningAmount=Decimal(str(lot['winningAmount'])),
                    feePercentage=Decimal(str(lot.get('feePercentage', default_fee_pct))),
                )
        return Response(InvoiceDetailSerializer(invoice).data, status=status.HTTP_201_CREATED)

    @staticmethod
    def _next_invoice_number():
        year = timezone.localdate().year
        prefix = f'INV-{year}-'
        existing = Invoice.objects.filter(invoiceNumber__startswith=prefix).values_list('invoiceNumber', flat=True)
        nums = [int(n.rsplit('-', 1)[1]) for n in existing if n.rsplit('-', 1)[1].isdigit()]
        return f'{prefix}{(max(nums) + 1 if nums else 1):03d}'
