from django.db import migrations, models
import django.db.models.deletion


def backfill_field(apps, schema_editor):
    AlarmRule = apps.get_model("devices", "AlarmRule")
    AlarmRule.objects.filter(field__isnull=True).update(field=models.F("metric"))


class Migration(migrations.Migration):

    dependencies = [
        ("devices", "0008_alarmrule_metric_recommendation_target_metric"),
    ]

    operations = [
        migrations.AddField(
            model_name="alarmrule",
            name="field",
            field=models.CharField(default="value", max_length=50),
        ),
        migrations.AlterField(
            model_name="alarmrule",
            name="metric",
            field=models.CharField(
                choices=[
                    ("temperature", "temperature"),
                    ("power_w", "power_w"),
                    ("reading", "reading"),
                    ("state", "state"),
                ],
                default="temperature",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="recommendation",
            name="target_metric",
            field=models.CharField(
                blank=True,
                choices=[
                    ("temperature", "temperature"),
                    ("power_w", "power_w"),
                    ("reading", "reading"),
                    ("state", "state"),
                ],
                max_length=20,
                null=True,
            ),
        ),
        migrations.RunPython(backfill_field, migrations.RunPython.noop),
    ]
