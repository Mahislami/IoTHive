from django.apps import AppConfig
from django.db import OperationalError, ProgrammingError
from django.db.models.signals import post_migrate

class DevicesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'devices'

    def ready(self):
        import devices.signals  # noqa: F401  # Connect signals
        from . import mqtt_security

        def bootstrap_mqtt_security(**kwargs):
            try:
                mqtt_security.ensure_all_devices_configured()
            except (OperationalError, ProgrammingError):
                # Database not ready; this signal will fire again after migrate succeeds.
                pass

        post_migrate.connect(bootstrap_mqtt_security, sender=self)
