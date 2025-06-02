from django.contrib.auth.models import User
from django.db import models

# Create your models here.

class Device(models.Model):
    DEVICE_TYPES = (
        ('sensor', 'Sensor'),
        ('actuator', 'Actuator'),
        ('light', 'Light'),
        ('thermostat', 'Thermostat'),
        ('switch', 'Switch'),
    )

    name = models.CharField(max_length=255)
    device_type = models.CharField(max_length=50, choices=DEVICE_TYPES)
    status = models.BooleanField(default=False)  # Example: On/Off
    topic = models.CharField(max_length=255, unique=True)  # MQTT topic
    created_at = models.DateTimeField(auto_now_add=True)

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