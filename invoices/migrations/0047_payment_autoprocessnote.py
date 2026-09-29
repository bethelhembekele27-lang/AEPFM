from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('invoices', '0046_alter_paymentreceiptfile_file')]
    operations = [
        migrations.AddField(
            model_name='payment', name='autoProcessNote',
            field=models.TextField(blank=True, default=''),
        ),
    ]
