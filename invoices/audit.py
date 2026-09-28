
from .models import AuditLog, SystemAuditLog


def log_audit(invoice, action_label, user, previous_value='', new_value='', reason='', action_type='other'):
    """
    One place that writes AuditLog rows, so every view stays consistent
    with what admin.py already enforces (read-only, code-created only).
    """
    profile = getattr(user, 'profile', None)
    role_name = profile.role.name if profile and profile.role else ''
    AuditLog.objects.create(
        invoice=invoice,
        action=action_label,
        actionType=action_type,
        performedBy=user if user and user.is_authenticated else None,
        userRole=role_name,
        previousValue=str(previous_value),
        newValue=str(new_value),
        reason=reason,
    )


def log_system_audit(user, action, target='', details=''):
    SystemAuditLog.objects.create(
        action=action,
        performedBy=user if user and user.is_authenticated else None,
        performedByName=(user.get_username() if user and user.is_authenticated else ''),
        target=target, details=details,
    )