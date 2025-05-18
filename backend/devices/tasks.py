from celery import shared_task
from .models import Device
import random
import json
import paho.mqtt.publish as publish

MQTT_BROKER = 'mosquitto-broker'
MQTT_PORT = 1883

@shared_task
def simulate_device_activity():
    devices = Device.objects.all()

    for device in devices:
        topic = device.topic or f"iot/sensors/{device.device_type}/{device.id}"

        payload = {
            "device": device.name,
            "type": device.device_type
        }

        if device.device_type == 'sensor':
            payload["reading"] = random.randint(20, 100)

        elif device.device_type == 'light':
            new_status = random.choice([0, 1])
            device.status = new_status
            device.save()
            payload["status"] = new_status
            

        elif device.device_type == 'switch':
            payload["state"] = random.choice([0, 1])

        elif device.device_type == 'thermostat':
            payload["temperature"] = round(random.uniform(18.0, 25.0), 1)

        elif device.device_type == 'actuator':
            payload["position"] = random.randint(0, 100)

        else:
            payload["message"] = "Unknown device update"

        publish.single(topic, json.dumps(payload), hostname=MQTT_BROKER, port=MQTT_PORT)
        print(f"[MQTT] Published to {topic}: {payload}")
