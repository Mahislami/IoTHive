from copy import deepcopy
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction

from devices.models import Device, UserProfile, AlarmRule
from devices.appliances import APPLIANCE_DEVICE_TYPES


GENERAL_DEVICE_BLUEPRINTS = [
    {
        "name": "Warehouse Thermostat",
        "device_type": "thermostat",
        "topic": "iot/sensors/warehouse/thermostat",
        "status": True,
        "power_rating_watts": 150,
        "current_power_watts": 9.4,
        "target_temperature": 22.0,
        "current_temperature": 21.5,
        "mode": "auto",
        "metadata": {"zone": "A1", "humidity_pct": 42},
    },
    {
        "name": "Factory Floor Sensor",
        "device_type": "sensor",
        "topic": "iot/sensors/factory/ambient",
        "status": True,
        "power_rating_watts": 8,
        "current_power_watts": 2.1,
        "metadata": {"reading": 68, "unit": "dB"},
    },
    {
        "name": "Exterior Lighting",
        "device_type": "light",
        "topic": "iot/lighting/exterior",
        "status": True,
        "power_rating_watts": 45,
        "current_power_watts": 32.0,
        "mode": "evening",
        "metadata": {"lumens": 800, "auto_mode": True},
    },
    {
        "name": "Pump Station Switch",
        "device_type": "switch",
        "topic": "iot/switch/pump-station",
        "status": False,
        "power_rating_watts": 15,
        "current_power_watts": 0.5,
        "metadata": {"last_service": "2024-01-10"},
    },
]

KITCHEN_DEVICE_BLUEPRINTS = [
    {
        "name": "Smart Oven",
        "device_type": "oven",
        "topic": "iot/power/kitchen/oven/main",
        "status": True,
        "power_rating_watts": 3200,
        "current_power_watts": 1480.0,
        "target_temperature": 200.0,
        "current_temperature": 185.0,
        "mode": "bake",
        "metadata": {
            "cycle": "bake",
            "cycle_progress": 18.0,
            "max_temperature_c": 260,
            "shelf_levels": 4,
            "has_convection": True,
        },
    },
    {
        "name": "Washer - Laundry Bay",
        "device_type": "washing_machine",
        "topic": "iot/power/kitchen/wash/1",
        "status": True,
        "power_rating_watts": 2000,
        "current_power_watts": 980.0,
        "target_temperature": 45.0,
        "current_temperature": 42.5,
        "mode": "warm",
        "metadata": {
            "cycle": "wash",
            "cycle_progress": 55.0,
            "drum_capacity_kg": 9.0,
            "spin_speed_rpm": 1000,
        },
    },
    {
        "name": "Kettle - Break Area",
        "device_type": "kettle",
        "topic": "iot/power/kitchen/kettle/alpha",
        "status": False,
        "power_rating_watts": 2200,
        "current_power_watts": 2.0,
        "target_temperature": 95.0,
        "current_temperature": 68.0,
        "mode": "keep-warm",
        "metadata": {
            "cycle": "boil",
            "cycle_progress": 0,
            "capacity_liters": 1.7,
            "keep_warm_minutes": 20,
        },
    },
    {
        "name": "Walk-in Fridge",
        "device_type": "fridge",
        "topic": "iot/power/kitchen/fridge/main",
        "status": True,
        "power_rating_watts": 180,
        "current_power_watts": 124.0,
        "target_temperature": 4.0,
        "current_temperature": 4.3,
        "mode": "normal",
        "metadata": {
            "cycle": "cool",
            "cycle_progress": 64.0,
            "volume_liters": 620,
            "has_ice_maker": True,
        },
    },
]

ALARM_BLUEPRINTS = [
    {
        "topic": "iot/power/kitchen/oven/main",
        "max_value": 240.0,
        "severity": "warn",
        "note": "Notify if oven exceeds safe cooking temperature.",
    },
    {
        "topic": "iot/power/kitchen/fridge/main",
        "max_value": 10.0,
        "severity": "crit",
        "note": "Critical alert if fridge begins to warm.",
    },
    {
        "topic": "iot/sensors/warehouse/thermostat",
        "max_value": 28.0,
        "min_value": 18.0,
        "severity": "warn",
        "note": "Thermostat drift outside comfort band.",
    },
]


class Command(BaseCommand):
    help = "Seed demo users, devices, and alarm rules for IoTHive."

    def handle(self, *args, **options):
        with transaction.atomic():
            admin = self._ensure_demo_admin()
            devices = []
            devices.extend(self._upsert_devices(GENERAL_DEVICE_BLUEPRINTS))
            devices.extend(self._upsert_devices(KITCHEN_DEVICE_BLUEPRINTS))
            self._ensure_alarm_rules(devices, admin)

        self.stdout.write(self.style.SUCCESS("Demo data seeded successfully."))
        self.stdout.write(
            "Default demo admin credentials -> username: demo_admin / password: admin123 (update after login)."
        )

    def _ensure_demo_admin(self):
        User = get_user_model()
        admin_defaults = {
            "email": "demo_admin@example.com",
            "is_staff": True,
            "is_superuser": False,
        }
        admin_user, created = User.objects.get_or_create(username="demo_admin", defaults=admin_defaults)
        if created:
            self.stdout.write("Created demo admin user 'demo_admin'.")
        if not admin_user.has_usable_password():
            admin_user.set_password("admin123")
            admin_user.save(update_fields=["password"])
        UserProfile.objects.update_or_create(user=admin_user, defaults={"role": "admin"})
        return admin_user

    def _upsert_devices(self, blueprints):
        upserted = []
        for blueprint in blueprints:
            data = deepcopy(blueprint)
            topic = data.pop("topic")
            metadata = data.pop("metadata", {})

            device, created = Device.objects.update_or_create(
                topic=topic,
                defaults={**data, "metadata": metadata},
            )
            msg = "Created" if created else "Updated"
            self.stdout.write(f"{msg} device '{device.name}' ({device.device_type}).")
            upserted.append(device)
        return upserted

    def _ensure_alarm_rules(self, devices, admin_user):
        topic_map = {device.topic: device for device in devices}
        for rule in ALARM_BLUEPRINTS:
            device = topic_map.get(rule["topic"])
            if not device:
                continue
            defaults = {
                "active": True,
                "created_by": admin_user,
                "min_value": rule.get("min_value"),
                "max_value": rule.get("max_value"),
                "expected_state": rule.get("expected_state"),
                "severity": rule.get("severity", "warn"),
                "note": rule.get("note", ""),
            }
            AlarmRule.objects.update_or_create(device=device, defaults=defaults)
            self.stdout.write(f"Configured alarm rule for {device.name}.")
