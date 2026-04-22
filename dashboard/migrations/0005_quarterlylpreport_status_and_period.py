from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0004_startupupdate_source_metadata'),
    ]

    operations = [
        migrations.AddField(
            model_name='quarterlylpreport',
            name='report_period_label',
            field=models.CharField(blank=True, max_length=32, null=True),
        ),
        migrations.AddField(
            model_name='quarterlylpreport',
            name='status',
            field=models.CharField(choices=[('Draft', 'Draft'), ('Published', 'Published')], default='Draft', max_length=16),
        ),
    ]
