import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0021_populate_invoice_publictoken'),
    ]

    operations = [
        migrations.AlterField(
            model_name='invoice',
            name='publicToken',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
