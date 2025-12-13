from django.db import migrations, models


def forward_fill_metrics(apps, schema_editor):
    AlarmRule = apps.get_model("devices", "AlarmRule")
    Recommendation = apps.get_model("devices", "Recommendation")

    for rule in AlarmRule.objects.all():
        if rule.expected_state is not None:
            rule.metric = "state"
        else:
            rule.metric = "temperature"
        rule.save(update_fields=["metric"])

    for rec in Recommendation.objects.all():
        if rec.target_expected_state is not None:
            rec.target_metric = "state"
        elif rec.target_min_value is not None or rec.target_max_value is not None:
            rec.target_metric = "temperature"
        rec.save(update_fields=["target_metric"])


class Migration(migrations.Migration):

    dependencies = [
        ("devices", "0007_recommendation_confidence"),
    ]

    operations = [
        migrations.AddField(
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
        migrations.AddField(
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
        migrations.RunPython(forward_fill_metrics, migrations.RunPython.noop),
    ]
