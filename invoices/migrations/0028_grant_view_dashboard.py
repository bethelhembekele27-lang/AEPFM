from django.db import migrations

ROLE_NAMES = ['Administrator', 'Auction Manager', 'Finance Manager', 'Viewer']
KEY = 'view_dashboard'


def grant(apps, schema_editor):
    Role = apps.get_model('invoices', 'Role')
    StaffProfile = apps.get_model('invoices', 'StaffProfile')
    for role in Role.objects.filter(name__in=ROLE_NAMES):
        if KEY not in role.defaultPrivileges:
            role.defaultPrivileges = [*role.defaultPrivileges, KEY]
            role.save(update_fields=['defaultPrivileges'])
    for profile in StaffProfile.objects.filter(role__name__in=ROLE_NAMES):
        if KEY not in profile.privileges:
            profile.privileges = [*profile.privileges, KEY]
            profile.save(update_fields=['privileges'])


def revoke(apps, schema_editor):
    Role = apps.get_model('invoices', 'Role')
    StaffProfile = apps.get_model('invoices', 'StaffProfile')
    for role in Role.objects.filter(name__in=ROLE_NAMES):
        role.defaultPrivileges = [p for p in role.defaultPrivileges if p != KEY]
        role.save(update_fields=['defaultPrivileges'])
    for profile in StaffProfile.objects.filter(role__name__in=ROLE_NAMES):
        profile.privileges = [p for p in profile.privileges if p != KEY]
        profile.save(update_fields=['privileges'])


class Migration(migrations.Migration):
    dependencies = [
        ('invoices', '0027_grant_call_operator_send_sms'),
    ]
    operations = [
        migrations.RunPython(grant, revoke),
    ]