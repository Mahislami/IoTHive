from django.contrib.auth.models import User
from django.db import models
from django.conf import settings
from django.utils import timezone
# Create your models here.

class Device(models.Model):
    DEVICE_TYPES = (
        ('sensor', 'Sensor'),
        ('actuator', 'Actuator'),
        ('light', 'Light'),
        ('thermostat', 'Thermostat'),
        ('switch', 'Switch'),
        ('dishwasher', 'Dishwasher'),
        ('washing_machine', 'Washing Machine'),
        ('dryer', 'Dryer'),
        ('oven', 'Oven'),
        ('microwave', 'Microwave'),
        ('kettle', 'Kettle'),
        ('gas', 'Gas Range'),
        ('fridge', 'Fridge'),
    )

    name = models.CharField(max_length=255)
    device_type = models.CharField(max_length=50, choices=DEVICE_TYPES)
    status = models.BooleanField(default=False)  # Example: On/Off
    topic = models.CharField(max_length=255, unique=True)  # MQTT topic
    created_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(blank=True, null=True)  # per-device extra config/state
    power_rating_watts = models.PositiveIntegerField(default=0)
    current_power_watts = models.FloatField(default=0)
    target_temperature = models.FloatField(null=True, blank=True)
    current_temperature = models.FloatField(null=True, blank=True)
    mode = models.CharField(max_length=32, blank=True, default='')

    def __str__(self):
        return f"{self.name} ({self.device_type})"
    
class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('operator', 'Operator'),
        ('visitor', 'Visitor'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)

    def __str__(self):
        return f"{self.user.username} ({self.role})"
    
class AlarmRule(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='alarm_rules')
    active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name='created_alarm_rules')
    # numeric (sensor/thermostat)
    min_value = models.FloatField(null=True, blank=True)
    max_value = models.FloatField(null=True, blank=True)
    # boolean (switch/light/actuator)
    expected_state = models.BooleanField(null=True, blank=True)

    severity = models.CharField(max_length=10, choices=[('info','Info'),('warn','Warning'),('crit','Critical')], default='warn')
    note = models.CharField(max_length=200, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=['device', 'active'])]

class AlarmEvent(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='alarm_events')
    rule = models.ForeignKey(AlarmRule, on_delete=models.SET_NULL, null=True, related_name='events')
    message = models.CharField(max_length=240)
    severity = models.CharField(max_length=10, choices=[('info','Info'),('warn','Warning'),('crit','Critical')], default='warn')
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
