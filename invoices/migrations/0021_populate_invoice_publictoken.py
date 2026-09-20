import uuid
from django.db import migrations


def populate_tokens(apps, schema_editor):
    Invoice = apps.get_model('invoices', 'Invoice')
    for pk in Invoice.objects.filter(publicToken__isnull=True).values_list('pk', flat=True):
        Invoice.objects.filter(pk=pk).update(publicToken=uuid.uuid4())


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0020_alter_invoice_callnotes_alter_payment_paymentmethod'),
    ]

    operations = [
        migrations.RunPython(populate_tokens, migrations.RunPython.noop),
    ]
