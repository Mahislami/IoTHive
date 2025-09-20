import json
import paho.mqtt.publish as mqtt_publish
from django.conf import settings

MQTT_BROKER = 'mosquitto-broker'
MQTT_PORT = 1883


def publish_device_update_like_simulator(device, override_status=None):
    """
    Publish an update using the same topic/payload conventions as simulate_device_activity().
    - topic: device.topic or f"iot/sensors/{device.device_type}/{device.id}"
    - payload keys:
        sensor -> (no random reading here; just base fields)
        light  -> status: 0/1
        switch -> state: 0/1
        thermostat -> temperature (use current metadata if you store it; otherwise omit)
        actuator -> x,y,position from metadata if present (no random movement)
    """
    topic = device.topic or f"iot/sensors/{device.device_type}/{device.id}"

    payload = {
        "device": device.name,
        "type": device.device_type,
    }

    # Only set fields that make sense on a manual update:
    if device.device_type == "light":
        # Simulator uses numeric status 0/1
        val = int(bool(override_status if override_status is not None else device.status))
        payload["status"] = val

    elif device.device_type == "switch":
        # Simulator uses "state" 0/1 for switch
        val = int(bool(override_status if override_status is not None else device.status))
        payload["state"] = val

    elif device.device_type == "thermostat":
        # No random value; include if stored somewhere (optional)
        meta = {}
        try:
            if device.metadata:
                meta = json.loads(device.metadata)
        except Exception:
            meta = {}
        if "temperature" in meta:
            payload["temperature"] = meta["temperature"]

    elif device.device_type == "actuator":
        # Mirror simulator: emit x,y,position if present in metadata (no movement here)
        meta = {}
        try:
            if device.metadata:
                meta = json.loads(device.metadata)
        except Exception:
            meta = {}
        x = meta.get("x")
        y = meta.get("y")
        if x is not None and y is not None:
            payload["x"] = x
            payload["y"] = y
            payload["position"] = int(((x + y) / 2) * 10)

    # For sensors and unknown types we just send the base fields (no random numbers)

    mqtt_publish.single(
        topic,
        json.dumps(payload),
        hostname=MQTT_BROKER,
        port=MQTT_PORT,
    )
