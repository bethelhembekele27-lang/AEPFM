from rest_framework.permissions import BasePermission, SAFE_METHODS

# ---------------------------------------------------------------------------
# Role -> allowed actions. Role slugs match the frontend exactly:
# administrator / auction_manager / finance_manager / call_operator / viewer
# ---------------------------------------------------------------------------
ROLE_PERMISSIONS = {
    'generate_invoice':      ['administrator', 'auction_manager'],   # her PDF_ROLES
    'upload_payment_proof':  ['administrator', 'auction_manager'],   # her "Upload receipt" button
    'verify_payment':        ['administrator', 'finance_manager'],
    'manager_verify_receipt': ['administrator', 'auction_manager'],  # reviewing bidder-submitted receipts, Phase 1
    'reject_payment':        ['administrator', 'finance_manager'],
    'mark_paid':              ['administrator', 'finance_manager'],
    'mark_overdue':           ['administrator', 'finance_manager'],  # manual override; automated version is the management command
    'change_status_generic': ['administrator', 'finance_manager'],   # her canChangeStatus() — the click-to-edit status badge, and the shared endpoint behind Verify/Reject/Mark paid/Mark overdue
    'extend_due_date':       ['administrator'],
    'add_remarks':           ['administrator', 'auction_manager', 'finance_manager', 'call_operator'],
    'manage_call_center': ['administrator', 'call_operator'],
    'view_dashboard':        ['administrator', 'auction_manager', 'finance_manager', 'viewer'],
    'view_reports':          ['administrator', 'auction_manager', 'finance_manager', 'viewer'],
    'view_audit':            ['administrator', 'auction_manager', 'finance_manager', 'viewer'],
    'delete_records':        ['administrator'],
    'manage_users':          ['administrator'],
    'manage_fee_config':     ['administrator'],
    'override_status':       ['administrator'],
    'edit_invoice':          ['administrator'],
}

# ---------------------------------------------------------------------------
# Status machine — locked statuses only move via override_status (admin).
# ---------------------------------------------------------------------------
LOCKED_STATUSES = ['paid', 'cancelled', 'waived']

ALLOWED_TRANSITIONS = {
    'invoice_generated':  ['pending_payment', 'cancelled', 'waived'],
    'pending_payment':    ['payment_submitted', 'overdue', 'cancelled', 'waived'],
    'payment_submitted':  ['under_verification', 'pending_payment'],
    'under_verification': ['paid', 'pending_payment'],
    'paid':               [],
    'overdue':            ['pending_payment', 'cancelled', 'waived'],
    'cancelled':          [],
    'waived':              [],
}


def has_permission(user, action):
    """
    Checks the user's effective privileges JSON list first (the new
    dynamic system) for any of the 11 catalog keys. Falls back to the
    original static ROLE_PERMISSIONS dict for actions outside the
    catalog (mark_paid, extend_due_date, delete_records, etc.), which
    still key off the role's name mapped back to the old role slugs.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    profile = getattr(user, 'profile', None)
    if profile is None:
        return False

    from .privileges import PRIVILEGE_KEYS
    if action in PRIVILEGE_KEYS:
        return action in (profile.privileges or [])

    role_slug_map = {
        'Administrator': 'administrator', 'Auction Manager': 'auction_manager',
        'Finance Manager': 'finance_manager', 'CRM / Call Center Officer': 'call_operator',
        'Viewer': 'viewer',
    }
    legacy_role = role_slug_map.get(profile.role.name, profile.role.name)
    return legacy_role in ROLE_PERMISSIONS.get(action, [])


def can_transition(current_status, new_status, user):
    """
    Admin bypasses the state machine entirely — matches "Admin can move any
    invoice to any status" from the spec. Everyone else has to follow
    ALLOWED_TRANSITIONS, which is what makes paid/cancelled/waived "locked"
    for non-admins: their transition lists are empty.
    """
    if has_permission(user, 'override_status'):
        return True
    return new_status in ALLOWED_TRANSITIONS.get(current_status, [])


# ---------------------------------------------------------------------------
# DRF permission classes for step 16's views
# ---------------------------------------------------------------------------

class ReadOnlyForViewer(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        profile = getattr(request.user, 'profile', None)
        return profile is not None and profile.role.name != 'Viewer'


class ActionPermissionMap(BasePermission):
    """
    For a ViewSet where different actions need different role checks. Set
    on the view:

        action_permissions = {
            'destroy': 'delete_records',
            'generate_pdf': 'generate_invoice',
        }

    Actions not listed pass through (still gated by ReadOnlyForViewer and
    IsAuthenticated) — only list the ones that need restricting beyond
    "any logged-in staff member."
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        action_map = getattr(view, 'action_permissions', {})
        required_action = action_map.get(getattr(view, 'action', None))
        if required_action is None:
            return True
        return has_permission(request.user, required_action)