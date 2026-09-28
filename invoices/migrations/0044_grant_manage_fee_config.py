from django.db import migrations
KEY = 'manage_fee_config'

def grant(apps, schema_editor):
    Role = apps.get_model('invoices', 'Role'); StaffProfile = apps.get_model('invoices', 'StaffProfile')
    for role in Role.objects.filter(name='Administrator'):
        if KEY not in role.defaultPrivileges:
            role.defaultPrivileges = [*role.defaultPrivileges, KEY]; role.save(update_fields=['defaultPrivileges'])
    for p in StaffProfile.objects.filter(role__name='Administrator'):
        if KEY not in p.privileges:
            p.privileges = [*p.privileges, KEY]; p.save(update_fields=['privileges'])

def revoke(apps, schema_editor):
    Role = apps.get_model('invoices', 'Role'); StaffProfile = apps.get_model('invoices', 'StaffProfile')
    for r in Role.objects.all():
        r.defaultPrivileges = [k for k in r.defaultPrivileges if k != KEY]; r.save(update_fields=['defaultPrivileges'])
    for p in StaffProfile.objects.all():
        p.privileges = [k for k in p.privileges if k != KEY]; p.save(update_fields=['privileges'])

class Migration(migrations.Migration):
    dependencies = [('invoices', '0043_verifyetcheck_pendingduplicate_and_more')]
    operations = [migrations.RunPython(grant, revoke)]
