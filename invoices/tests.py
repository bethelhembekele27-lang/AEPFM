from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone
from unittest.mock import patch, MagicMock
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token

# Tests only — never settings.py, so production password hashing is untouched.
# PBKDF2 costs ~2s per make_user on this machine and make_user runs several
# times per test, which dominated the suite's runtime. MD5 is fast and
# cryptographically irrelevant here: these hashes are discarded with the
# test database and never authenticate a real login.
FAST_PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

from invoices.models import (
    Role, StaffProfile, Winner, Invoice, InvoiceLot, AuditLog, Payment,
    VerifyEtCheck, VerifyEtAutomationSettings,
)
from django.core.files.uploadedfile import SimpleUploadedFile


def make_user(username, role_name, privileges):
    role, _ = Role.objects.get_or_create(
        name=role_name,
        defaults={'defaultPrivileges': privileges, 'isBuiltIn': True},
    )
    user = User.objects.create_user(username=username, password='testpass123')
    StaffProfile.objects.create(user=user, role=role, privileges=privileges, isActive=True)
    return user


def make_invoice(status='pending_payment'):
    winner = Winner.objects.create(
        bidderName='Test Bidder',
        winnerPhone='251911000000',
        winningAmount=1000,
    )
    invoice = Invoice.objects.create(
        winner=winner,
        invoiceNumber=f'INV-TEST-{winner.id}-{status}',
        invoiceDate='2026-01-01',
        dueDate='2026-01-15',
        status=status,
    )
    InvoiceLot.objects.create(
        invoice=invoice,
        lotNumber='L1',
        auctionName='Test Auction',
        winningAmount=1000,
        feePercentage=5,
    )
    return invoice


@override_settings(PASSWORD_HASHERS=FAST_PASSWORD_HASHERS)
class PrivilegeGateTests(TestCase):
    """
    Hits each role against each privilege-gated endpoint and asserts who gets
    in (200) vs blocked (403). Every one of these corresponds to a real bug
    found by hand in an earlier session.

    Plain django.test.TestCase rather than DRF's APITestCase: APITestCase
    derives from TransactionTestCase, which flushes the whole database after
    every test and dominated the suite's runtime. TestCase wraps each test in
    a transaction instead, and we only need header-based token auth (not
    APITestCase's login machinery) — but the client must still be an
    APIClient, since Django's default test client is not DRF-aware.
    """

    def setUp(self):
        self.client = APIClient()
        self.viewer = make_user('viewer_t', 'Viewer', ['view_invoices', 'view_dashboard'])
        self.finance = make_user('finance_t', 'Finance Manager', [
            'view_invoices', 'edit_invoice', 'generate_invoice', 'change_status_generic',
            'verify_payment', 'view_dashboard', 'view_reports', 'view_audit', 'view_paid_only',
        ])
        self.call_op = make_user('callop_t', 'CRM / Call Center Officer', [
            'view_invoices', 'edit_invoice', 'generate_invoice', 'change_status_generic',
            'verify_payment', 'manage_call_center', 'view_call_center_dashboard',
            'view_reports', 'send_sms', 'delete_records', 'extend_due_date',
            'upload_payment_proof',
        ])
        self.admin = make_user('admin_t', 'Administrator', [
            'view_invoices', 'edit_invoice', 'generate_invoice', 'change_status_generic',
            'verify_payment', 'import_batches', 'view_dashboard', 'view_reports',
            'view_audit', 'manage_call_center', 'view_call_center_dashboard',
            'manage_users', 'manager_verify_receipt', 'send_sms', 'delete_records',
            'extend_due_date', 'upload_payment_proof',
        ])
        self.invoice = make_invoice()

    def auth(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def test_dashboard_summary_allowed_with_privilege(self):
        self.auth(self.viewer)
        res = self.client.get('/api/invoices/summary/')
        self.assertEqual(res.status_code, 200)

    def test_dashboard_summary_blocked_without_privilege(self):
        bare = make_user('bare_t', 'Viewer', ['view_invoices'])
        self.auth(bare)
        res = self.client.get('/api/invoices/summary/')
        self.assertEqual(res.status_code, 403)

    def test_extend_due_date_blocked_without_privilege(self):
        self.auth(self.viewer)
        res = self.client.post(
            f'/api/invoices/{self.invoice.id}/extend-due-date/',
            {'dueDate': '2026-02-01'},
        )
        self.assertEqual(res.status_code, 403)

    def test_extend_due_date_allowed_with_privilege(self):
        self.auth(self.call_op)
        res = self.client.post(
            f'/api/invoices/{self.invoice.id}/extend-due-date/',
            {'dueDate': '2026-02-01'},
        )
        self.assertEqual(res.status_code, 200)

    def test_delete_invoice_blocked_without_privilege(self):
        self.auth(self.finance)  # finance has no delete_records
        res = self.client.delete(f'/api/invoices/{self.invoice.id}/')
        self.assertEqual(res.status_code, 403)

    def test_delete_invoice_allowed_for_admin(self):
        inv = make_invoice()
        self.auth(self.admin)
        res = self.client.delete(f'/api/invoices/{inv.id}/')
        self.assertEqual(res.status_code, 204)

    def test_delete_invoice_allowed_for_call_center(self):
        """Call Center holds delete_records, so the API must accept it."""
        inv = make_invoice()
        self.auth(self.call_op)
        res = self.client.delete(f'/api/invoices/{inv.id}/')
        self.assertEqual(res.status_code, 204)

    def test_employee_create_blocked_for_non_admin(self):
        self.auth(self.finance)
        res = self.client.post('/api/employees/', {
            'fullName': 'X',
            'username': 'x',
            'password': 'x',
            'roleId': self.viewer.profile.role.id,
        })
        self.assertEqual(res.status_code, 403)

    def test_login_returns_privileges(self):
        res = self.client.post('/api/auth/login/', {
            'username': 'finance_t',
            'password': 'testpass123',
        })
        self.assertEqual(res.status_code, 200)
        self.assertIn('privileges', res.data)
        self.assertIn('verify_payment', res.data['privileges'])

    def test_finance_operations_list_only_shows_paid(self):
        make_invoice(status='paid')
        make_invoice(status='pending_payment')
        self.auth(self.finance)
        res = self.client.get('/api/invoices/')
        self.assertEqual(res.status_code, 200)
        rows = res.data.get('results', res.data)
        self.assertTrue(rows)
        self.assertTrue(all(r['status'] == 'paid' for r in rows))

    def test_admin_operations_list_is_not_restricted(self):
        """The paid-only filter is Finance-scoped; admin must still see all."""
        make_invoice(status='paid')
        make_invoice(status='pending_payment')
        self.auth(self.admin)
        res = self.client.get('/api/invoices/')
        self.assertEqual(res.status_code, 200)
        rows = res.data.get('results', res.data)
        self.assertTrue(any(r['status'] == 'pending_payment' for r in rows))

    def test_call_center_note_writes_audit_log(self):
        self.auth(self.call_op)
        res = self.client.post(
            f'/api/call-center/{self.invoice.id}/note/',
            {'callNotes': 'Called and confirmed.'},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(
            AuditLog.objects.filter(
                invoice=self.invoice,
                actionType='add_call_note',
            ).exists()
        )


@override_settings(PASSWORD_HASHERS=FAST_PASSWORD_HASHERS)
class VerifyEtCheckTests(TestCase):
    """
    Exercises POST /api/receipts/<id>/verify-transaction/ itself.

    check_transaction is mocked in every test, so the suite never touches
    verify.et regardless of what VERIFY_ET_API_KEY happens to be set to
    locally or in CI. Mocking at the check_transaction boundary (rather
    than at requests.post) keeps these tests independent of the HTTP call
    shape inside verify_et.py.
    """

    NOT_CONFIGURED = 'Verify.ET is not configured on this server.'

    def setUp(self):
        # APIClient, not django.test.Client — DRF auth needs the DRF client.
        self.client = APIClient()
        from django.test import override_settings
        self.override = override_settings(VERIFY_ET_API_KEY='', VERIFY_ET_SETTLEMENT_ACCOUNTS={})
        self.override.enable()
        self.addCleanup(self.override.disable)

        self.reviewer = make_user('vet_reviewer', 'CRM / Call Center Officer', [
            'view_invoices', 'verify_payment', 'manager_verify_receipt',
        ])
        self.outsider = make_user('vet_outsider', 'Viewer', ['view_invoices'])
        self.invoice = make_invoice()
        self.payment = Payment.objects.create(
            invoice=self.invoice,
            amountPaid=1000,
            paymentMethod='bank_transfer',
            paymentDate='2026-01-15',
        )

    def mock_provider(self, result=None, error=None):
        """Patch check_transaction to return (result, error) — no network."""
        return patch('invoices.services.verify_et.check_transaction', return_value=(result, error))

    def auth(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def url(self, payment=None):
        return f"/api/receipts/{(payment or self.payment).id}/verify-transaction/"

    def test_not_configured_returns_502_not_crash(self):
        self.auth(self.reviewer)
        with self.mock_provider(error=self.NOT_CONFIGURED):
            res = self.client.post(self.url(), {'bank': 'cbe', 'referenceNumber': 'FT1234567890'}, format='json')
        self.assertEqual(res.status_code, 502)
        self.assertEqual(res.data['error'], self.NOT_CONFIGURED)

    def test_missing_reference_returns_400(self):
        self.auth(self.reviewer)
        with self.mock_provider(error='unused'):
            res = self.client.post(self.url(), {'bank': 'cbe'}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('reference number', res.data['error'])

    def test_blank_reference_returns_400(self):
        self.auth(self.reviewer)
        with self.mock_provider(error='unused'):
            res = self.client.post(self.url(), {'referenceNumber': '   '}, format='json')
        self.assertEqual(res.status_code, 400)

    def test_null_field_does_not_crash(self):
        """Explicit JSON nulls must not raise AttributeError on .strip()."""
        self.auth(self.reviewer)
        with self.mock_provider(error=self.NOT_CONFIGURED):
            res = self.client.post(self.url(), {
                'bank': None, 'referenceNumber': 'FT1', 'accountSuffix': None, 'phoneNumber': None,
            }, format='json')
        self.assertEqual(res.status_code, 502)

    def test_permission_denied_without_receipt_privileges(self):
        self.auth(self.outsider)
        with self.mock_provider(error='unused'):
            res = self.client.post(self.url(), {'referenceNumber': 'FT123'}, format='json')
        self.assertEqual(res.status_code, 403)

    def test_unknown_payment_returns_404(self):
        self.auth(self.reviewer)
        with self.mock_provider(error='unused'):
            res = self.client.post(
                '/api/receipts/99999999/verify-transaction/',
                {'referenceNumber': 'FT123'},
                format='json',
            )
        self.assertEqual(res.status_code, 404)

    def test_verify_payment_privilege_alone_is_enough(self):
        """Finance has verify_payment but not manager_verify_receipt."""
        finance = make_user('vet_finance', 'Finance Manager', ['view_invoices', 'verify_payment'])
        self.auth(finance)
        with self.mock_provider(error=self.NOT_CONFIGURED):
            res = self.client.post(self.url(), {'referenceNumber': 'FT123'}, format='json')
        self.assertEqual(res.status_code, 502)

    def test_no_check_record_created_when_not_configured(self):
        """A failed provider call must not leave a half-written check behind."""
        from invoices.models import VerifyEtCheck
        self.auth(self.reviewer)
        with self.mock_provider(error=self.NOT_CONFIGURED):
            self.client.post(self.url(), {'bank': 'cbe', 'referenceNumber': 'FT123'}, format='json')
        self.assertFalse(VerifyEtCheck.objects.filter(payment=self.payment).exists())

    def test_successful_check_is_persisted_and_returned(self):
        """Provider said yes: the record is written and echoed back."""
        from invoices.models import VerifyEtCheck
        provider_result = {
            'bank': 'cbe', 'requestId': 'req-1', 'processingStatus': 'completed',
            'verified': True, 'amount': '1235.00', 'currency': 'ETB',
            'senderName': 'Ashefi Birr', 'receiverName': 'Auction Ethiopia',
            'receiverAccount': '1000123', 'settlementMatched': True,
            'rawResponse': {'data': []}, 'errorMessage': '',
        }
        self.auth(self.reviewer)
        with self.mock_provider(result=provider_result):
            res = self.client.post(
                self.url(),
                {'bank': 'cbe', 'referenceNumber': 'FT123', 'accountSuffix': '43970701'},
                format='json',
            )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data['verified'], True)
        self.assertEqual(res.data['referenceNumber'], 'FT123')
        self.assertEqual(res.data['accountSuffix'], '43970701')
        self.assertNotIn('rawResponse', res.data)
        check = VerifyEtCheck.objects.get(payment=self.payment)
        self.assertEqual(check.checkedBy, self.reviewer)
        self.assertEqual(str(check.amount), '1235.00')

    def test_settlement_mismatch_is_null_without_settlement_account(self):
        """
        The red 'did not go to our account' warning fires on settlementMatched
        == False. That must only be trusted when we actually sent our own
        settlement account, so it has to stay None otherwise.
        """
        provider_result = {
            'bank': 'cbe', 'requestId': 'req-2', 'processingStatus': 'completed',
            'verified': True, 'amount': '1000.00', 'currency': 'ETB',
            'senderName': 'A', 'receiverName': 'B', 'receiverAccount': 'x',
            'settlementMatched': None,
            'rawResponse': {}, 'errorMessage': '',
        }
        self.auth(self.reviewer)
        with self.mock_provider(result=provider_result):
            res = self.client.post(self.url(), {'bank': 'cbe', 'referenceNumber': 'FT9'}, format='json')
        self.assertEqual(res.status_code, 201)
        self.assertIsNone(res.data['settlementMatched'])


@override_settings(PASSWORD_HASHERS=FAST_PASSWORD_HASHERS)
class StatusTransitionTests(TestCase):
    def test_locked_status_cannot_transition_for_non_admin(self):
        from invoices.permissions import can_transition
        finance = make_user('finance_t2', 'Finance Manager', ['change_status_generic'])
        self.assertFalse(can_transition('paid', 'pending_payment', finance))

    def test_admin_can_override_locked_status(self):
        from invoices.permissions import can_transition
        admin = make_user('admin_t2', 'Administrator', ['override_status'])
        self.assertTrue(can_transition('paid', 'pending_payment', admin))


class EthiopianCalendarTests(TestCase):
    """
    Pure date arithmetic — no DB or network. This module was previously
    untested despite its own docstring claiming the formula had been
    cross-checked by hand.
    """

    def test_new_year_anchor_leap_case(self):
        from invoices.services.ethiopian_calendar import ethiopian_to_gregorian
        self.assertEqual(ethiopian_to_gregorian(2016, 1, 1).isoformat(), '2023-09-12')

    def test_new_year_anchor_non_leap_case(self):
        from invoices.services.ethiopian_calendar import ethiopian_to_gregorian
        self.assertEqual(ethiopian_to_gregorian(2018, 1, 1).isoformat(), '2025-09-11')

    def test_pagume_day_range_enforced(self):
        from invoices.services.ethiopian_calendar import ethiopian_to_gregorian
        with self.assertRaises(ValueError):
            ethiopian_to_gregorian(2016, 13, 7)

    def test_month_13_day_6_is_valid(self):
        from invoices.services.ethiopian_calendar import ethiopian_to_gregorian
        self.assertTrue(ethiopian_to_gregorian(2016, 13, 6).isoformat())

    def test_day_31_rejected(self):
        from invoices.services.ethiopian_calendar import ethiopian_to_gregorian
        with self.assertRaises(ValueError):
            ethiopian_to_gregorian(2016, 1, 31)

    def test_parse_and_convert_valid_slash_date(self):
        from invoices.services.ethiopian_calendar import parse_and_convert
        self.assertTrue(parse_and_convert('16/12/2016').startswith('20'))

    def test_parse_and_convert_declines_modern_looking_year(self):
        """2020s is implausible as an Ethiopian year, so we decline."""
        from invoices.services.ethiopian_calendar import parse_and_convert
        self.assertIsNone(parse_and_convert('16/12/2026'))

    def test_parse_and_convert_short_year_normalized(self):
        from invoices.services.ethiopian_calendar import parse_and_convert
        self.assertEqual(parse_and_convert('16/12/16'), parse_and_convert('16/12/2016'))

    def test_parse_and_convert_rejects_unparseable_text(self):
        from invoices.services.ethiopian_calendar import parse_and_convert
        self.assertIsNone(parse_and_convert('Sep 25, 2026, 10:00 AM'))
        self.assertIsNone(parse_and_convert(''))
        self.assertIsNone(parse_and_convert(None))

    def test_parse_and_convert_tolerates_calendar_suffix(self):
        from invoices.services.ethiopian_calendar import parse_and_convert
        self.assertEqual(parse_and_convert('16/12/2016'), parse_and_convert('16/12/2016 ዓ.ም'))
        self.assertEqual(parse_and_convert('16/12/2016'), parse_and_convert('16/12/2016 E.C.'))


@override_settings(PASSWORD_HASHERS=FAST_PASSWORD_HASHERS, VERIFY_ET_API_KEY='k', VERIFY_ET_PROCESS_ASYNC=False,
                   VERIFY_ET_SETTLEMENT_ACCOUNTS={'cbe': '1000547266289'})
class VerifyEtAutomationTests(TestCase):
    def setUp(self):
        self.invoice = make_invoice(status='pending_payment')        # fee 50.00
        self.payment = self.new_payment(self.invoice)
        VerifyEtAutomationSettings.objects.create(autoVerificationEnabled=True, isActive=True)

    def new_payment(self, invoice):
        return Payment.objects.create(invoice=invoice, amountPaid=50, paymentMethod='bank_transfer',
            paymentDate='2026-01-15', submittedViaPublicLink=True, verificationStatus='pending_manager_review')

    def result(self, amount='50.00', **kw):
        r = {'bank': 'cbe', 'requestId': 'r', 'processingStatus': 'completed', 'verified': True, 'amount': amount,
             'currency': 'ETB', 'senderName': 'X', 'receiverName': 'AE', 'receiverAccount': 'x',
             'settlementMatched': True, 'rawResponse': {}, 'errorMessage': ''}
        r.update(kw); return r

    def run_it(self, result, payment=None, ref='FT1', bank='cbe'):
        from invoices.services.verify_et_automation import process_new_receipt
        payment = payment or self.payment
        with patch('invoices.services.verify_et_automation._get_or_extract', return_value=(ref, bank)), \
             patch('invoices.services.verify_et_automation.check_transaction', return_value=(result, None)) as m, \
             patch('invoices.services.verify_et_automation.send_sms') as sms:
            process_new_receipt(payment)
        payment.refresh_from_db(); payment.invoice.refresh_from_db()
        return m, sms

    def test_disabled_never_calls_provider(self):
        VerifyEtAutomationSettings.objects.all().update(autoVerificationEnabled=False)
        m, _ = self.run_it(self.result())
        m.assert_not_called()

    def test_match_approves_and_records_real_amount(self):
        self.run_it(self.result())
        self.assertEqual(self.payment.invoice.status, 'paid'); self.assertTrue(self.payment.autoReviewed)

    def test_underpaid_rejects_and_sms_states_shortfall(self):
        _, sms = self.run_it(self.result(amount='20.00'))
        self.assertEqual(self.payment.verificationStatus, 'manager_rejected')
        self.assertEqual(self.payment.amountDiscrepancy, 'underpaid')
        self.assertIn('30.00', sms.call_args[0][1])

    def test_overpaid_flagged_but_left_pending(self):
        _, sms = self.run_it(self.result(amount='80.00'))
        self.assertEqual(self.payment.verificationStatus, 'pending_manager_review')
        self.assertEqual(self.payment.amountDiscrepancy, 'overpaid'); sms.assert_not_called()

    def test_unconfirmed_account_left_pending(self):
        self.run_it(self.result(settlementMatched=None))
        self.assertEqual(self.payment.verificationStatus, 'pending_manager_review')

    def test_wrong_account_rejects(self):
        self.run_it(self.result(settlementMatched=False))
        self.assertEqual(self.payment.verificationStatus, 'manager_rejected')

    def test_not_found_is_never_auto_rejected(self):
        self.run_it(self.result(verified=False, amount=None))
        self.assertEqual(self.payment.verificationStatus, 'pending_manager_review')

    def test_non_cbe_receipt_skipped(self):
        m, _ = self.run_it(self.result(), bank='other'); m.assert_not_called()

    def test_reused_reference_blocks_decision(self):
        other = self.new_payment(make_invoice(status='paid')); other.verificationStatus = 'manager_approved'; other.save()
        VerifyEtCheck.objects.create(payment=other, bank='cbe', referenceNumber='FT1', verified=True, processingStatus='completed', countsAsUsed=True)
        self.run_it(self.result())
        self.assertEqual(self.payment.verificationStatus, 'pending_manager_review')

    def test_partial_payments_add_up(self):
        self.run_it(self.result(amount='20.00'), ref='FT1')                 # rejected, 30 still owed
        second = self.new_payment(self.invoice)
        self.run_it(self.result(amount='30.00'), payment=second, ref='FT2')
        self.assertEqual(second.verificationStatus, 'manager_approved')


@override_settings(PASSWORD_HASHERS=FAST_PASSWORD_HASHERS, VERIFY_ET_PROCESS_ASYNC=False)
class EndToEndInvoiceLifecycleTests(TestCase):
    """
    One real workflow through the actual public and authenticated APIs:
    invoice created -> bidder uploads receipt -> automation checks with
    Verify.ET (mocked) -> invoice auto-approved -> visible to staff.

    Only the external provider is mocked; the upload endpoint, automation
    engine, audit trail and read APIs all run for real.
    """

    def setUp(self):
        self.client = APIClient()
        self.admin = make_user('e2e_admin', 'Administrator', [
            'view_invoices', 'edit_invoice', 'generate_invoice', 'change_status_generic',
            'verify_payment', 'import_batches', 'view_dashboard', 'view_reports',
            'view_audit', 'manage_call_center', 'view_call_center_dashboard',
            'manage_users', 'manager_verify_receipt', 'send_sms', 'delete_records',
            'extend_due_date', 'upload_payment_proof',
        ])
        self.auth(self.admin)

    def auth(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def _make_invoice(self, lot_ref, amount='10000.00'):
        res = self.client.post('/api/winners/manual/', {
            'bidderName': 'E2E Tester', 'winnerPhone': '251911223344', 'companyName': '',
            'lots': [{'lotNumber': lot_ref, 'auctionName': 'E2E Auction', 'winningAmount': amount}],
        }, format='json')
        self.assertEqual(res.status_code, 201, res.content)
        return Invoice.objects.get(id=res.data['id'])

    def _submit_receipt(self, invoice, reference, verify_result):
        # The real public path: unauthenticated.
        self.client.credentials()
        fake_receipt = SimpleUploadedFile('receipt.jpg', b'\xff\xd8\xff' + (b'0' * 25000),
                                          content_type='image/jpeg')
        # Mock extraction to return the reference number
        with patch('invoices.public_views._validate_receipt_file', return_value=None), \
             patch('invoices.services.verify_et_automation.check_transaction',
                   return_value=(verify_result, None)), \
             patch('invoices.services.verify_et_automation._get_or_extract',
                   return_value=(reference, 'cbe')), \
             patch('invoices.services.verify_et_automation._set_note'):
            res = self.client.post(
                f'/api/public/invoice/{invoice.publicToken}/receipt/',
                {'receiptFiles': fake_receipt},
                format='multipart',
            )
        self.auth(self.admin)
        return res

    def _verify_result(self, invoice, **over):
        result = {
            'bank': 'cbe', 'requestId': 'e2e-req', 'processingStatus': 'completed',
            'verified': True, 'amount': str(invoice.totalAmount), 'currency': 'ETB',
            'senderName': 'E2E Tester', 'receiverName': 'Auction Ethiopia',
            'receiverAccount': '1000547266289', 'settlementMatched': True,
            'rawResponse': {}, 'errorMessage': '',
        }
        result.update(over)
        return result

    def test_full_lifecycle_auto_approved(self):
        VerifyEtAutomationSettings.objects.create(autoVerificationEnabled=True,
                                                  configuredBy=self.admin, isActive=True)
        invoice = self._make_invoice('E2E-1')

        res = self.client.get(f'/api/public/invoice/{invoice.publicToken}/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['invoiceNumber'], invoice.invoiceNumber)

        with override_settings(VERIFY_ET_API_KEY='test-key', GEMINI_API_KEY=''):
            res = self._submit_receipt(invoice, 'FT-E2E-0001', self._verify_result(invoice))
        self.assertEqual(res.status_code, 201, res.content)
        payment_id = res.data['paymentId']

        invoice.refresh_from_db()
        payment = Payment.objects.get(id=payment_id)
        self.assertEqual(invoice.status, 'paid')
        self.assertEqual(payment.verificationStatus, 'manager_approved')
        self.assertTrue(payment.autoReviewed)
        self.assertTrue(AuditLog.objects.filter(invoice=invoice,
                                                actionType='auto_verify_et').exists())

        res = self.client.get(f'/api/invoices/{invoice.id}/')
        self.assertEqual(res.data['status'], 'paid')
        res = self.client.get('/api/receipts/?verificationStatus=manager_approved')
        self.assertTrue(any(p['id'] == payment_id for p in res.data))

    def test_reused_reference_across_two_invoices_does_not_double_approve(self):
        VerifyEtAutomationSettings.objects.create(autoVerificationEnabled=True,
                                                  configuredBy=self.admin, isActive=True)

        def go(lot_ref):
            invoice = self._make_invoice(lot_ref, amount='5000.00')
            with override_settings(VERIFY_ET_API_KEY='test-key', GEMINI_API_KEY=''):
                res = self._submit_receipt(invoice, 'FT-SHARED-001',
                                          self._verify_result(invoice, requestId=f'req-{lot_ref}'))
            self.assertEqual(res.status_code, 201, res.content)
            invoice.refresh_from_db()
            return invoice, Payment.objects.get(id=res.data['paymentId'])

        invoice_1, payment_1 = go('DUP-1')
        self.assertEqual(invoice_1.status, 'paid')

        invoice_2, payment_2 = go('DUP-2')
        self.assertNotEqual(invoice_2.status, 'paid')
        self.assertFalse(payment_2.autoReviewed)
        self.assertTrue(payment_2.verifyEtCheck.possibleDuplicate)


@override_settings(PASSWORD_HASHERS=FAST_PASSWORD_HASHERS)
class ExportVerifiedWinnersTests(TestCase):
    """
    The companion-CRM export endpoint. The service key is the only auth
    path, so these cover both halves: that a valid key gets exactly the
    verified+paid set, and that no other credential gets through.
    """

    def setUp(self):
        self.client = APIClient()
        from invoices.services.service_keys import generate_service_api_key
        self.raw_key, self.key = generate_service_api_key('test-crm')

    def auth(self, key=None):
        return {'HTTP_AUTHORIZATION': f'Bearer {key or self.raw_key}'}

    def make_verified_payment(self):
        invoice = make_invoice(status='paid')
        payment = Payment.objects.create(
            invoice=invoice, amountPaid='1000.00', paymentMethod='bank_transfer',
            paymentDate='2026-01-15', verificationStatus='manager_approved',
            paymentStatus='verified', managerVerifiedDate=timezone.now(),
        )
        return invoice, payment

    def test_missing_header_401(self):
        res = self.client.get('/api/export/v1/verified-winners/')
        self.assertEqual(res.status_code, 401)

    def test_bad_key_401(self):
        res = self.client.get('/api/export/v1/verified-winners/', **self.auth('wrong'))
        self.assertEqual(res.status_code, 401)

    def test_revoked_key_401(self):
        self.key.isActive = False
        self.key.save(update_fields=['isActive'])
        res = self.client.get('/api/export/v1/verified-winners/', **self.auth())
        self.assertEqual(res.status_code, 401)

    def test_staff_token_is_not_accepted(self):
        """A staff login must not work here — separate trust boundary."""
        admin = make_user('exp_admin', 'Administrator', ['view_invoices', 'manage_users'])
        token, _ = Token.objects.get_or_create(user=admin)
        res = self.client.get('/api/export/v1/verified-winners/',
                              HTTP_AUTHORIZATION=f'Token {token.key}')
        self.assertEqual(res.status_code, 401)

    def test_only_verified_paid_winners_included(self):
        self.make_verified_payment()
        pending = make_invoice(status='pending_payment')
        Payment.objects.create(invoice=pending, amountPaid=500,
                               paymentMethod='bank_transfer', paymentDate='2026-01-15')
        res = self.client.get('/api/export/v1/verified-winners/', **self.auth())
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data['results']), 1)

    def test_paid_but_unapproved_payment_excluded(self):
        """Paid invoice with no approved Payment must not leak."""
        invoice = make_invoice(status='paid')
        Payment.objects.create(invoice=invoice, amountPaid=500,
                               paymentMethod='bank_transfer', paymentDate='2026-01-15',
                               verificationStatus='pending_manager_review')
        res = self.client.get('/api/export/v1/verified-winners/', **self.auth())
        self.assertEqual(len(res.data['results']), 0)

    def test_pagination(self):
        for _ in range(3):
            self.make_verified_payment()
        res = self.client.get('/api/export/v1/verified-winners/?limit=2', **self.auth())
        self.assertEqual(len(res.data['results']), 2)
        self.assertIsNotNone(res.data['nextCursor'])
        res2 = self.client.get(
            f'/api/export/v1/verified-winners/?limit=2&cursor={res.data["nextCursor"]}',
            **self.auth())
        self.assertEqual(len(res2.data['results']), 1)
        self.assertIsNone(res2.data['nextCursor'])

    def test_since_filters_out_earlier_entries(self):
        invoice, payment = self.make_verified_payment()
        payment.managerVerifiedDate = timezone.now() - timezone.timedelta(days=5)
        payment.save(update_fields=['managerVerifiedDate'])
        cutoff = (timezone.now() - timezone.timedelta(days=1)).isoformat()
        res = self.client.get(f'/api/export/v1/verified-winners/?since={cutoff}', **self.auth())
        self.assertEqual(len(res.data['results']), 0)

    def test_amount_is_string(self):
        self.make_verified_payment()
        res = self.client.get('/api/export/v1/verified-winners/', **self.auth())
        self.assertIsInstance(res.data['results'][0]['amountPaid'], str)

    def test_bad_limit_and_cursor_return_400_not_500(self):
        res = self.client.get('/api/export/v1/verified-winners/?limit=abc', **self.auth())
        self.assertEqual(res.status_code, 400)
        res = self.client.get('/api/export/v1/verified-winners/?cursor=%%%not-base64', **self.auth())
        self.assertEqual(res.status_code, 400)
        res = self.client.get('/api/export/v1/verified-winners/?since=not-a-date', **self.auth())
        self.assertEqual(res.status_code, 400)

    def test_lastUsedAt_updated(self):
        self.make_verified_payment()
        self.assertIsNone(self.key.lastUsedAt)
        self.client.get('/api/export/v1/verified-winners/', **self.auth())
        self.key.refresh_from_db()
        self.assertIsNotNone(self.key.lastUsedAt)

    def test_raw_key_is_never_stored(self):
        from invoices.models import ServiceApiKey
        import hashlib
        self.assertNotIn(self.raw_key, ServiceApiKey.objects.get(pk=self.key.pk).hashedKey)
        self.assertEqual(
            hashlib.sha256(self.raw_key.encode()).hexdigest(),
            self.key.hashedKey,
        )
