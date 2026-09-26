from django.db import migrations

KEY = 'view_paid_only'
ROLE_NAME = 'Finance Manager'


def grant(apps, schema_editor):
    Role = apps.get_model('invoices', 'Role')
    StaffProfile = apps.get_model('invoices', 'StaffProfile')
    for role in Role.objects.filter(name=ROLE_NAME):
        if KEY not in role.defaultPrivileges:
            role.defaultPrivileges = [*role.defaultPrivileges, KEY]
            role.save(update_fields=['defaultPrivileges'])
    for profile in StaffProfile.objects.filter(role__name=ROLE_NAME):
        if KEY not in profile.privileges:
            profile.privileges = [*profile.privileges, KEY]
            profile.save(update_fields=['privileges'])


def revoke(apps, schema_editor):
    Role = apps.get_model('invoices', 'Role')
    StaffProfile = apps.get_model('invoices', 'StaffProfile')
    for role in Role.objects.filter(name=ROLE_NAME):
        role.defaultPrivileges = [p for p in role.defaultPrivileges if p != KEY]
        role.save(update_fields=['defaultPrivileges'])
    for profile in StaffProfile.objects.filter(role__name=ROLE_NAME):
        profile.privileges = [p for p in profile.privileges if p != KEY]
        profile.save(update_fields=['privileges'])


class Migration(migrations.Migration):
    dependencies = [
        ('invoices', '0034_receiptextraction_bankreferencenumber_verifyetcheck'),
    ]
    operations = [
        migrations.RunPython(grant, revoke),
    ]