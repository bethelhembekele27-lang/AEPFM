from django.db import migrations

NEW_KEYS = ['upload_payment_proof']
GRANT_TO_ROLES = ['Administrator', 'CRM / Call Center Officer']


def grant(apps, schema_editor):
    Role = apps.get_model('invoices', 'Role')
    StaffProfile = apps.get_model('invoices', 'StaffProfile')
    for role in Role.objects.filter(name__in=GRANT_TO_ROLES):
        changed = False
        for key in NEW_KEYS:
            if key not in role.defaultPrivileges:
                role.defaultPrivileges = [*role.defaultPrivileges, key]
                changed = True
        if changed:
            role.save(update_fields=['defaultPrivileges'])
    for profile in StaffProfile.objects.filter(role__name__in=GRANT_TO_ROLES):
        changed = False
        for key in NEW_KEYS:
            if key not in profile.privileges:
                profile.privileges = [*profile.privileges, key]
                changed = True
        if changed:
            profile.save(update_fields=['privileges'])


def revoke(apps, schema_editor):
    Role = apps.get_model('invoices', 'Role')
    StaffProfile = apps.get_model('invoices', 'StaffProfile')
    for role in Role.objects.filter(name__in=GRANT_TO_ROLES):
        role.defaultPrivileges = [p for p in role.defaultPrivileges if p not in NEW_KEYS]
        role.save(update_fields=['defaultPrivileges'])
    for profile in StaffProfile.objects.filter(role__name__in=GRANT_TO_ROLES):
        profile.privileges = [p for p in profile.privileges if p not in NEW_KEYS]
        profile.save(update_fields=['privileges'])


class Migration(migrations.Migration):
    dependencies = [
        ('invoices', '0031_grant_delete_extend_call_center'),
    ]
    operations = [
        migrations.RunPython(grant, revoke),
    ]