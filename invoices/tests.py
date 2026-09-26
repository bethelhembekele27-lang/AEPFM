from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework.authtoken.models import Token

from invoices.models import Role, StaffProfile, Winner, Invoice, InvoiceLot, AuditLog


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


class PrivilegeGateTests(APITestCase):
    """
    Hits each role against each privilege-gated endpoint and asserts who gets
    in (200) vs blocked (403). Every one of these corresponds to a real bug
    found by hand in an earlier session.
    """

    def setUp(self):
        self.viewer = make_user('viewer_t', 'Viewer', ['view_invoices', 'view_dashboard'])
        self.finance = make_user('finance_t', 'Finance Manager', [
            'view_invoices', 'edit_invoice', 'generate_invoice', 'change_status_generic',
            'verify_payment', 'view_dashboard', 'view_reports', 'view_audit',
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


class StatusTransitionTests(TestCase):
    def test_locked_status_cannot_transition_for_non_admin(self):
        from invoices.permissions import can_transition
        finance = make_user('finance_t2', 'Finance Manager', ['change_status_generic'])
        self.assertFalse(can_transition('paid', 'pending_payment', finance))

    def test_admin_can_override_locked_status(self):
        from invoices.permissions import can_transition
        admin = make_user('admin_t2', 'Administrator', ['override_status'])
        self.assertTrue(can_transition('paid', 'pending_payment', admin))
