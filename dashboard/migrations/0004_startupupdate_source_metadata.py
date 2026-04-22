# Source event time, ingestion run time, and source channel for startup updates.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0003_alter_startup_options'),
    ]

    operations = [
        migrations.AddField(
            model_name='startupupdate',
            name='source_type',
            field=models.CharField(blank=True, max_length=32, null=True),
        ),
        migrations.AddField(
            model_name='startupupdate',
            name='source_occurred_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='startupupdate',
            name='ingestion_ran_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
