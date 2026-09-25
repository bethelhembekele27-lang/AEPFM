from django.db import migrations

GRANTS = {
    'Finance Manager': ['edit_invoice', 'generate_invoice'],
    'CRM / Call Center Officer': ['view_invoices', 'edit_invoice', 'generate_invoice', 'change_status_generic', 'verify_payment'],
}
REVOKES = {
    'Viewer': ['view_audit'],
}


def apply_changes(apps, schema_editor):
    Role = apps.get_model('invoices', 'Role')
    StaffProfile = apps.get_model('invoices', 'StaffProfile')

    for role_name, keys in GRANTS.items():
        for role in Role.objects.filter(name=role_name):
            merged = list(role.defaultPrivileges)
            merged += [k for k in keys if k not in merged]
            role.defaultPrivileges = merged
            role.save(update_fields=['defaultPrivileges'])
        for profile in StaffProfile.objects.filter(role__name=role_name):
            merged = list(profile.privileges)
            merged += [k for k in keys if k not in merged]
            profile.privileges = merged
            profile.save(update_fields=['privileges'])

    for role_name, keys in REVOKES.items():
        for role in Role.objects.filter(name=role_name):
            role.defaultPrivileges = [p for p in role.defaultPrivileges if p not in keys]
            role.save(update_fields=['defaultPrivileges'])
        for profile in StaffProfile.objects.filter(role__name=role_name):
            profile.privileges = [p for p in profile.privileges if p not in keys]
            profile.save(update_fields=['privileges'])


def reverse_changes(apps, schema_editor):
    Role = apps.get_model('invoices', 'Role')
    StaffProfile = apps.get_model('invoices', 'StaffProfile')

    for role_name, keys in GRANTS.items():
        for role in Role.objects.filter(name=role_name):
            role.defaultPrivileges = [p for p in role.defaultPrivileges if p not in keys]
            role.save(update_fields=['defaultPrivileges'])
        for profile in StaffProfile.objects.filter(role__name=role_name):
            profile.privileges = [p for p in profile.privileges if p not in keys]
            profile.save(update_fields=['privileges'])

    for role_name, keys in REVOKES.items():
        for role in Role.objects.filter(name=role_name):
            merged = list(role.defaultPrivileges)
            merged += [k for k in keys if k not in merged]
            role.defaultPrivileges = merged
            role.save(update_fields=['defaultPrivileges'])
        for profile in StaffProfile.objects.filter(role__name=role_name):
            merged = list(profile.privileges)
            merged += [k for k in keys if k not in merged]
            profile.privileges = merged
            profile.save(update_fields=['privileges'])


class Migration(migrations.Migration):
    dependencies = [
        ('invoices', '0028_grant_view_dashboard'),
    ]
    operations = [
        migrations.RunPython(apply_changes, reverse_changes),
    ]