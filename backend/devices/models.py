import json

from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.core import exceptions
from django.utils import timezone
from django.utils.translation import gettext as gettext_now

try:
    from django.db.models import JSONField as BuiltinJSONField
except ImportError:  # Django < 3.1, fall back to simple TextField-based implementation
    class BuiltinJSONField(models.TextField):
        description = _("JSON")

        def from_db_value(self, value, expression, connection):
            if value is None or isinstance(value, (dict, list)):
                return value
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value

        def to_python(self, value):
            if value is None or isinstance(value, (dict, list)):
                return value
            try:
                return json.loads(value)
            except json.JSONDecodeError as exc:
                raise exceptions.ValidationError(_("Invalid JSON data")) from exc

        def get_prep_value(self, value):
            if value is None:
                return value
            if isinstance(value, (dict, list)):
                return json.dumps(value, ensure_ascii=False)
            return value

# Create your models here.

class Device(models.Model):
    DEVICE_TYPES = (
        ('sensor', _('Sensor')),
        ('actuator', _('Actuator')),
        ('light', _('Light')),
        ('thermostat', _('Thermostat')),
        ('switch', _('Switch')),
        ('dishwasher', _('Dishwasher')),
        ('washing_machine', _('Washing Machine')),
        ('dryer', _('Dryer')),
        ('oven', _('Oven')),
        ('microwave', _('Microwave')),
        ('kettle', _('Kettle')),
        ('gas', _('Gas Range')),
        ('fridge', _('Fridge')),
        ('tv', _('TV')),
    )

    name = models.CharField(max_length=255)
    device_type = models.CharField(max_length=50, choices=DEVICE_TYPES)
    status = models.BooleanField(default=False)  # Example: On/Off
    topic = models.CharField(max_length=255, unique=True)  # MQTT topic
    created_at = models.DateTimeField(auto_now_add=True)
    metadata = BuiltinJSONField(blank=True, null=True)  # per-device extra config/state
    power_rating_watts = models.PositiveIntegerField(default=0)
    current_power_watts = models.FloatField(default=0)
    target_temperature = models.FloatField(null=True, blank=True)
    current_temperature = models.FloatField(null=True, blank=True)
    mode = models.CharField(max_length=32, blank=True, default='')

    def __str__(self):
        return f"{self.name} ({self.device_type})"
    
class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('admin', _('Admin')),
        ('operator', _('Operator')),
        ('visitor', _('Visitor')),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)

    def __str__(self):
        return f"{self.user.username} ({self.role})"
    
class MetricChoices(models.TextChoices):
    TEMPERATURE = "temperature", _("temperature")
    POWER_W = "power_w", _("power_w")
    READING = "reading", _("reading")
    STATE = "state", _("state")


class AlarmRule(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='alarm_rules')
    active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name='created_alarm_rules')
    metric = models.CharField(
        max_length=20,
        choices=MetricChoices.choices,
        default=MetricChoices.TEMPERATURE,
    )
    field = models.CharField(max_length=50, default="value")
    # numeric (sensor/thermostat)
    min_value = models.FloatField(null=True, blank=True)
    max_value = models.FloatField(null=True, blank=True)
    # boolean (switch/light/actuator)
    expected_state = models.BooleanField(null=True, blank=True)

    severity = models.CharField(
        max_length=10,
        choices=[
            ('info', _('Info')),
            ('warn', _('Warning')),
            ('crit', _('Critical')),
        ],
        default='warn',
    )
    note = models.CharField(max_length=200, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=['device', 'active'])]

class AlarmEvent(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='alarm_events')
    rule = models.ForeignKey(AlarmRule, on_delete=models.SET_NULL, null=True, related_name='events')
    message = models.CharField(max_length=240)
    severity = models.CharField(
        max_length=10,
        choices=[
            ('info', _('Info')),
            ('warn', _('Warning')),
            ('crit', _('Critical')),
        ],
        default='warn',
    )
    observed_value = models.CharField(max_length=64, blank=True, default='')
    is_active = models.BooleanField(default=True)
    acknowledged = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    cleared_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['device', 'is_active']),
            models.Index(fields=['severity', 'is_active']),
        ]

    def clear(self):
        self.is_active = False
        self.cleared_at = timezone.now()
        self.save(update_fields=['is_active', 'cleared_at'])

    @property
    def localized_message(self):
        """
        Render the alarm message using the active locale instead of the
        stored English text, so alarms respect the viewer's language.
        """
        rule = self.rule
        device_name = self.device.name if self.device else ''

        if rule:
            metric = rule.metric or MetricChoices.TEMPERATURE

            if metric != MetricChoices.STATE:
                try:
                    observed_val = float(self.observed_value)
                except (TypeError, ValueError):
                    observed_val = None

                if observed_val is not None:
                    if rule.min_value is not None and observed_val < rule.min_value:
                        return gettext_now("%(device)s: value %(value)s below %(threshold)s") % {
                            "device": device_name,
                            "value": observed_val,
                            "threshold": rule.min_value,
                        }
                    if rule.max_value is not None and observed_val > rule.max_value:
                        return gettext_now("%(device)s: value %(value)s above %(threshold)s") % {
                            "device": device_name,
                            "value": observed_val,
                            "threshold": rule.max_value,
                        }

            if metric == MetricChoices.STATE and rule.expected_state is not None:
                state_value = self.observed_value or ('on' if rule.expected_state else 'off')
                return gettext_now("%(device)s: state is %(state)s") % {
                    "device": device_name,
                    "state": gettext_now(state_value),
                }

        return self.message


class Recommendation(models.Model):
    KIND_CHOICES = [
        ('alarm_rule', _('Alarm Rule')),
        ('control', _('Control Suggestion')),
    ]
    SEVERITY_CHOICES = [
        ('info', _('Info')),
        ('warn', _('Warning')),
        ('crit', _('Critical')),
    ]

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='recommendations')
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True, default='')
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default='alarm_rule')
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='warn')

    # Target rule fields (used when "Implement" is clicked)
    target_min_value = models.FloatField(null=True, blank=True)
    target_max_value = models.FloatField(null=True, blank=True)
    target_expected_state = models.BooleanField(null=True, blank=True)
    target_severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='warn')
    target_note = models.CharField(max_length=200, blank=True, default='')
    target_metric = models.CharField(
        max_length=20,
        choices=MetricChoices.choices,
        null=True,
        blank=True,
    )
    confidence = models.FloatField(default=0.5)

    acknowledged = models.BooleanField(default=False)
    implemented = models.BooleanField(default=False)
    dismissed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['device', 'dismissed']),
        ]

    def __str__(self):
        return f"{self.title} ({self.device.name})"
