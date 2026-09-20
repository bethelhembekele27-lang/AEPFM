"""Single source of truth for the 11-item privilege grid — both the
Employees/Roles UI and has_permission() read from this."""

PRIVILEGE_CATALOG = [
    {'key': 'view_invoices', 'label': 'View invoices & winner records', 'category': 'Processing Fees'},
    {'key': 'edit_invoice', 'label': 'Edit invoice details / winner records', 'category': 'Processing Fees'},
    {'key': 'generate_invoice', 'label': 'Generate invoice PDF', 'category': 'Processing Fees'},
    {'key': 'change_status_generic', 'label': 'Change payment status', 'category': 'Processing Fees'},
    {'key': 'verify_payment', 'label': 'Verify / reject payments', 'category': 'Processing Fees'},
    {'key': 'import_batches', 'label': 'Import new bid data batches', 'category': 'Processing Fees'},
    {'key': 'view_reports', 'label': 'Generate custom reports', 'category': 'Reports'},
    {'key': 'view_audit', 'label': 'View audit trail', 'category': 'Reports'},
    {'key': 'manage_call_center', 'label': 'Manage CRM / call center inquiries', 'category': 'CRM'},
    {'key': 'view_call_center_dashboard', 'label': 'View call center payment dashboard', 'category': 'CRM'},
    {'key': 'manage_users', 'label': 'Manage employee accounts & privileges', 'category': 'Administration'},

    # Phase 1: reviewing bidder-submitted receipts (public-link uploads)
    # for legitimacy, before Finance ever sees them. Deliberately separate
    # from 'verify_payment' — that stays Finance's own step for
    # staff-entered payments. This one is planned to eventually be
    # automated, so it's kept as its own distinct privilege.
    {'key': 'manager_verify_receipt', 'label': 'Review bidder-submitted receipts', 'category': 'Processing Fees'},
    {'key': 'send_sms', 'label': 'Send invoice SMS to bidders', 'category': 'Processing Fees'},
]

PRIVILEGE_KEYS = {p['key'] for p in PRIVILEGE_CATALOG}

BUILT_IN_ROLE_DEFAULTS = {
    'Administrator': [p['key'] for p in PRIVILEGE_CATALOG],
    'Auction Manager': [
        'view_invoices', 'edit_invoice', 'generate_invoice', 'import_batches',
        'view_reports', 'view_audit', 'manager_verify_receipt', 'send_sms',
    ],
    'Finance Manager': ['view_invoices', 'change_status_generic', 'verify_payment', 'view_reports', 'view_audit'],
    'CRM / Call Center Officer': ['manage_call_center', 'view_call_center_dashboard', 'view_reports'],
    'Viewer': ['view_invoices', 'view_audit'],
}