from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0017_grant_manager_verify_receipt'),
    ]

    operations = [
        migrations.AddField(
            model_name='importbatch',
            name='columnMapping',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]