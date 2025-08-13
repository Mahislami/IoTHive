from celery import shared_task
from .models import Device
import random
import json
import paho.mqtt.publish as publish

MQTT_BROKER = 'mosquitto-broker'
MQTT_PORT = 1883
# Define actuator movement bounds (room size)
ROOM_WIDTH = 10
ROOM_HEIGHT = 10

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
        # Initialize coordinates in device.metadata if needed
            if not device.metadata:
                device.metadata = json.dumps({"x": random.randint(0, ROOM_WIDTH), "y": random.randint(0, ROOM_HEIGHT)})
    
            meta = json.loads(device.metadata)
            x = meta.get("x", 0)
            y = meta.get("y", 0)

            # Simulate small movement
            dx = random.choice([-1, 0, 1])
            dy = random.choice([-1, 0, 1])
            new_x = max(0, min(ROOM_WIDTH, x + dx))
            new_y = max(0, min(ROOM_HEIGHT, y + dy))

            # Update metadata
            meta["x"] = new_x
            meta["y"] = new_y
            device.metadata = json.dumps(meta)
            device.save()

            payload["x"] = new_x
            payload["y"] = new_y
            payload["position"] = int((new_x + new_y) / 2 * 10)  # Optional: combined "position" metric

        else:
            payload["message"] = "Unknown device update"

        publish.single(topic, json.dumps(payload), hostname=MQTT_BROKER, port=MQTT_PORT)
        print(f"[MQTT] Published to {topic}: {payload}")
