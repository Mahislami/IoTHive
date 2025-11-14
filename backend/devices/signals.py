from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import UserProfile, Device
from .mqtt_security import ensure_device_security_assets, remove_device_security_assets

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=Device)
def ensure_device_mqtt_credentials(sender, instance, **kwargs):
    ensure_device_security_assets(instance)


@receiver(post_delete, sender=Device)
def cleanup_device_mqtt_credentials(sender, instance, **kwargs):
    remove_device_security_assets(instance)
