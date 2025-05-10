# backend/devices/tasks.py

from celery import shared_task
from .models import Device
import random
import paho.mqtt.publish as publish

MQTT_BROKER = 'mosquitto-broker'
MQTT_PORT = 1883

@shared_task
def simulate_device_activity():
    devices = Device.objects.all()

    for device in devices:
        topic = device.topic or f"devices/{device.device_type}/{device.id}"

        if device.device_type == 'sensor':
            reading = random.randint(20, 100)
            payload = f"{device.name} reading: {reading}"

        elif device.device_type == 'light':
            new_status = random.choice([True, False])
            device.status = new_status
            device.save()
            payload = f"{device.name} turned {'ON' if new_status else 'OFF'}"

        elif device.device_type == 'switch':
            new_state = random.choice(['on', 'off'])
            payload = f"{device.name} switched {new_state}"

        elif device.device_type == 'thermostat':
            temperature = round(random.uniform(18.0, 25.0), 1)
            payload = f"{device.name} temperature set to {temperature}°C"

        elif device.device_type == 'actuator':
            position = random.randint(0, 100)
            payload = f"{device.name} actuator moved to position {position}"

        else:
            payload = f"{device.name} sent an unknown update"

        publish.single(topic, payload, hostname=MQTT_BROKER, port=MQTT_PORT)
        print(f"[MQTT] Published to {topic}: {payload}")
