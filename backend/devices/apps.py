from django.apps import AppConfig

class DevicesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'devices'

    def ready(self):
        import devices.signals  # 👈 Connect the signal when app is ready
