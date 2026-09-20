from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status as http_status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .audit import log_audit
from .models import Invoice, SmsLog
from .permissions import has_permission
from .sms import build_message, normalize_phone, public_link, send_sms

MIN_DAYS = 1
MAX_DAYS = 90
MAX_MESSAGE_LENGTH = 600
DUPLICATE_WINDOW_SECONDS = 60   # guards against a double-click sending (and paying for) two SMS


def _clamp_days(days):
    return max(MIN_DAYS, min(MAX_DAYS, days))


def _default_days(invoice):
    """First send: the configured default (14). Resend: the days left until the current
    deadline, so sending again keeps the deadline unless staff type a different number."""
    today = timezone.localdate()
    if invoice.smsSentAt and invoice.dueDate > today:
        return _clamp_days((invoice.dueDate - today).days)
    return _clamp_days(settings.SMS_DEFAULT_DUE_DAYS)


def _parse_days(raw, default):
    if raw in (None, ''):
        return default
    try:
        days = int(raw)
    except (TypeError, ValueError):
        raise ValueError('The number of days must be a whole number.')
    if not MIN_DAYS <= days <= MAX_DAYS:
        raise ValueError(f'The number of days must be between {MIN_DAYS} and {MAX_DAYS}.')
    return days


def _state_problem(invoice):
    if invoice.status == 'invoice_generated':
        return 'Generate the invoice PDF first, then send the SMS.'
    if invoice.status in ('paid', 'cancelled', 'waived'):
        return f'This invoice is {invoice.status}, so no SMS can be sent.'
    return None


def _forbidden():
    return Response({'error': 'You do not have permission to send SMS.'}, status=http_status.HTTP_403_FORBIDDEN)


class SmsPreviewView(APIView):
    """GET /api/invoices/<id>/sms/preview/?dueDays=14 - what would be sent. No side effects."""
    permission_classes = [IsAuthenticated]

    def get(self, request, invoice_id):
        if not has_permission(request.user, 'send_sms'):
            return _forbidden()
        invoice = get_object_or_404(Invoice.objects.select_related('winner'), pk=invoice_id)

        problem = _state_problem(invoice)
        if problem:
            return Response({'error': problem}, status=http_status.HTTP_400_BAD_REQUEST)
        try:
            days = _parse_days(request.query_params.get('dueDays'), _default_days(invoice))
        except ValueError as exc:
            return Response({'error': str(exc)}, status=http_status.HTTP_400_BAD_REQUEST)

        due_date = timezone.localdate() + timedelta(days=days)
        link = public_link(invoice)
        return Response({
            'invoiceNumber': invoice.invoiceNumber,
            'bidderName': invoice.winner.bidderName,
            'rawPhone': invoice.winner.winnerPhone,
            'phone': normalize_phone(invoice.winner.winnerPhone),
            'link': link,
            'dueDays': days,
            'dueDate': due_date.isoformat(),
            'message': build_message(invoice, link, due_date),
            'smsSentAt': invoice.smsSentAt,
            'smsSendCount': invoice.smsSendCount,
            'backend': settings.SMS_BACKEND,
        })


class SmsSendView(APIView):
    """POST /api/invoices/<id>/sms/send/ {message, dueDays} - send, log, set the deadline."""
    permission_classes = [IsAuthenticated]

    def post(self, request, invoice_id):
        if not has_permission(request.user, 'send_sms'):
            return _forbidden()
        invoice = get_object_or_404(Invoice.objects.select_related('winner'), pk=invoice_id)

        problem = _state_problem(invoice)
        if problem:
            return Response({'error': problem}, status=http_status.HTTP_400_BAD_REQUEST)

        phone_override = str(request.data.get('phone', '')).strip()
        raw_phone_to_check = phone_override or invoice.winner.winnerPhone
        phone = normalize_phone(raw_phone_to_check)
        if not phone:
            return Response(
                {'error': f'"{raw_phone_to_check}" is not a valid Ethiopian mobile number.'},
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        if phone_override and phone_override != invoice.winner.winnerPhone:
            previous_phone = invoice.winner.winnerPhone
            invoice.winner.winnerPhone = phone_override
            invoice.winner.save(update_fields=['winnerPhone'])
            log_audit(
                invoice, 'Update winner phone number', request.user,
                previous_phone, phone_override,
                reason='Edited while sending SMS', action_type='other',
            )

        message = str(request.data.get('message', '')).strip()
        if not message:
            return Response({'error': 'The message is empty.'}, status=http_status.HTTP_400_BAD_REQUEST)
        if len(message) > MAX_MESSAGE_LENGTH:
            return Response({'error': f'The message is longer than {MAX_MESSAGE_LENGTH} characters.'}, status=http_status.HTTP_400_BAD_REQUEST)

        try:
            days = _parse_days(request.data.get('dueDays'), _default_days(invoice))
        except ValueError as exc:
            return Response({'error': str(exc)}, status=http_status.HTTP_400_BAD_REQUEST)

        recently_sent = SmsLog.objects.filter(
            invoice=invoice, success=True,
            sentAt__gte=timezone.now() - timedelta(seconds=DUPLICATE_WINDOW_SECONDS),
        ).exists()
        if recently_sent:
            return Response(
                {'error': 'An SMS was sent for this invoice a moment ago. Wait a minute before sending again.'},
                status=http_status.HTTP_409_CONFLICT,
            )

        success, provider_response = send_sms(phone, message)

        if not success:
            SmsLog.objects.create(
                invoice=invoice, phone=phone, message=message, success=False,
                providerResponse=provider_response[:2000], sentBy=request.user,
            )
            return Response({'error': f'The SMS was not sent. {provider_response}'}, status=http_status.HTTP_502_BAD_GATEWAY)

        previous_due = invoice.dueDate
        new_due = timezone.localdate() + timedelta(days=days)
        previous_status = invoice.status
        with transaction.atomic():
            SmsLog.objects.create(
                invoice=invoice, phone=phone, message=message, success=True,
                providerResponse=provider_response[:2000], sentBy=request.user,
            )
            if invoice.status == 'overdue':
                invoice.status = 'pending_payment'
            invoice.smsSentAt = timezone.now()
            invoice.smsSendCount += 1
            invoice.dueDate = new_due
            invoice.save(update_fields=['status', 'smsSentAt', 'smsSendCount', 'dueDate', 'updatedAt'])
            log_audit(
                invoice, 'SMS sent to bidder', request.user,
                previous_value=previous_due, new_value=new_due,
                reason=f'SMS #{invoice.smsSendCount} to +{phone}; payment due in {days} days.'
                       + (f' Status changed from overdue to pending_payment.' if previous_status == 'overdue' else ''),
                action_type='send_sms',
            )

        return Response({
            'success': True,
            'smsSentAt': invoice.smsSentAt,
            'smsSendCount': invoice.smsSendCount,
            'dueDate': str(new_due),
            'backend': settings.SMS_BACKEND,
        })


class BulkSmsSendView(APIView):
    """POST /api/invoices/sms/bulk-send/ {invoiceIds: [...], dueDays?: N}
    Sends the auto-generated message to each invoice, skipping ineligible
    ones (bad phone, wrong status, sent moments ago). Used by Operations
    bulk-select, Import Batch bulk-send, and the eventual cutover backfill."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not has_permission(request.user, 'send_sms'):
            return _forbidden()
        invoice_ids = request.data.get('invoiceIds', [])
        override_days = request.data.get('dueDays')
        sent, skipped = [], []

        for invoice_id in invoice_ids:
            try:
                invoice = Invoice.objects.select_related('winner').get(pk=invoice_id)
            except Invoice.DoesNotExist:
                skipped.append({'invoiceId': invoice_id, 'reason': 'Not found'})
                continue

            problem = _state_problem(invoice)
            if problem:
                skipped.append({'invoiceId': invoice_id, 'invoiceNumber': invoice.invoiceNumber, 'reason': problem})
                continue

            phone = normalize_phone(invoice.winner.winnerPhone)
            if not phone:
                skipped.append({'invoiceId': invoice_id, 'invoiceNumber': invoice.invoiceNumber, 'reason': f'Invalid phone: {invoice.winner.winnerPhone}'})
                continue

            try:
                days = _parse_days(override_days, _default_days(invoice))
            except ValueError as exc:
                skipped.append({'invoiceId': invoice_id, 'invoiceNumber': invoice.invoiceNumber, 'reason': str(exc)})
                continue

            if SmsLog.objects.filter(invoice=invoice, success=True, sentAt__gte=timezone.now() - timedelta(seconds=DUPLICATE_WINDOW_SECONDS)).exists():
                skipped.append({'invoiceId': invoice_id, 'invoiceNumber': invoice.invoiceNumber, 'reason': 'Sent moments ago'})
                continue

            due_date = timezone.localdate() + timedelta(days=days)
            message = build_message(invoice, public_link(invoice), due_date)
            success, provider_response = send_sms(phone, message)

            if not success:
                SmsLog.objects.create(invoice=invoice, phone=phone, message=message, success=False, providerResponse=provider_response[:2000], sentBy=request.user)
                skipped.append({'invoiceId': invoice_id, 'invoiceNumber': invoice.invoiceNumber, 'reason': f'Send failed: {provider_response}'})
                continue

            previous_due, previous_status = invoice.dueDate, invoice.status
            with transaction.atomic():
                SmsLog.objects.create(invoice=invoice, phone=phone, message=message, success=True, providerResponse=provider_response[:2000], sentBy=request.user)
                if invoice.status == 'overdue':
                    invoice.status = 'pending_payment'
                invoice.smsSentAt = timezone.now()
                invoice.smsSendCount += 1
                invoice.dueDate = due_date
                invoice.save(update_fields=['status', 'smsSentAt', 'smsSendCount', 'dueDate', 'updatedAt'])
                log_audit(invoice, 'SMS sent to bidder (bulk)', request.user, previous_value=previous_due, new_value=due_date,
                          reason=f'Bulk SMS #{invoice.smsSendCount} to +{phone}; due in {days} days.', action_type='send_sms')
            sent.append({'invoiceId': invoice_id, 'invoiceNumber': invoice.invoiceNumber, 'phone': phone, 'dueDate': str(due_date)})

        return Response({'sent': sent, 'skipped': skipped})
