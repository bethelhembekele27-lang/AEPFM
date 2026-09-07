from django.db import migrations


def grant_privilege(apps, schema_editor):
    Role = apps.get_model('invoices', 'Role')
    StaffProfile = apps.get_model('invoices', 'StaffProfile')

    roles_to_update = Role.objects.filter(name__in=['Administrator', 'Auction Manager'])
    for role in roles_to_update:
        if 'manager_verify_receipt' not in role.defaultPrivileges:
            role.defaultPrivileges = [*role.defaultPrivileges, 'manager_verify_receipt']
            role.save(update_fields=['defaultPrivileges'])

    # Also backfill any existing employees already assigned to those roles,
    # so current Administrators/Auction Managers get the privilege
    # immediately rather than only on their next privilege edit.
    profiles_to_update = StaffProfile.objects.filter(role__name__in=['Administrator', 'Auction Manager'])
    for profile in profiles_to_update:
        if 'manager_verify_receipt' not in profile.privileges:
            profile.privileges = [*profile.privileges, 'manager_verify_receipt']
            profile.save(update_fields=['privileges'])


def revoke_privilege(apps, schema_editor):
    Role = apps.get_model('invoices', 'Role')
    StaffProfile = apps.get_model('invoices', 'StaffProfile')

    for role in Role.objects.filter(name__in=['Administrator', 'Auction Manager']):
        if 'manager_verify_receipt' in role.defaultPrivileges:
            role.defaultPrivileges = [p for p in role.defaultPrivileges if p != 'manager_verify_receipt']
            role.save(update_fields=['defaultPrivileges'])

    for profile in StaffProfile.objects.filter(role__name__in=['Administrator', 'Auction Manager']):
        if 'manager_verify_receipt' in profile.privileges:
            profile.privileges = [p for p in profile.privileges if p != 'manager_verify_receipt']
            profile.save(update_fields=['privileges'])


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0016_invoice_publictoken_payment_managernote_and_more'),
    ]

    operations = [
        migrations.RunPython(grant_privilege, revoke_privilege),
    ]