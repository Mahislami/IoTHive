from django.core.management.base import BaseCommand

from devices.models import Device
from devices import mqtt_security


class Command(BaseCommand):
    help = "Ensure each device has a TLS cert/key pair and ACL entry for Mosquitto."

    def handle(self, *args, **options):
        devices = list(Device.objects.order_by("id"))
        if not devices:
            self.stdout.write(self.style.WARNING("No devices found; ACL still refreshed."))
        for device in devices:
            mqtt_security.ensure_device_security_assets(device, resync_acl=False)
        mqtt_security.sync_acl(devices=devices)
        self.stdout.write(self.style.SUCCESS("MQTT certificates and ACLs are up to date."))
