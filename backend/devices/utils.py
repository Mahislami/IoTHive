import json
import os
import ssl
import paho.mqtt.publish as mqtt_publish


def load_device_metadata(device):
    """Return metadata as a mutable dict regardless of storage format."""
    meta = device.metadata
    if isinstance(meta, dict):
        return dict(meta)
    if not meta:
        return {}
    if isinstance(meta, str):
        try:
            return json.loads(meta)
        except json.JSONDecodeError:
            return {}
    return dict(meta)


def save_device_metadata(device, meta, *, update_fields=("metadata",)):
    device.metadata = meta
    device.save(update_fields=list(update_fields))

MQTT_BROKER = os.environ.get("MQTT_BROKER", "mosquitto-broker")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "8883"))
MQTT_TLS_ENABLED = os.environ.get("MQTT_TLS_ENABLED", "true").lower() not in {"0", "false", "no"}
MQTT_CA_CERT = os.environ.get("MQTT_CA_CERT", "/certs/ca.crt")
MQTT_CLIENT_CERT = os.environ.get("MQTT_CLIENT_CERT", "/certs/backend-client.crt")
MQTT_CLIENT_KEY = os.environ.get("MQTT_CLIENT_KEY", "/certs/backend-client.key")

MQTT_TLS_CONFIG = None
if MQTT_TLS_ENABLED:
    MQTT_TLS_CONFIG = {
        "ca_certs": MQTT_CA_CERT,
        "certfile": MQTT_CLIENT_CERT,
        "keyfile": MQTT_CLIENT_KEY,
        "tls_version": ssl.PROTOCOL_TLSv1_2,
        "cert_reqs": ssl.CERT_REQUIRED,
    }

MQTT_PUBLISH_KWARGS = {}
if MQTT_TLS_CONFIG:
    MQTT_PUBLISH_KWARGS["tls"] = MQTT_TLS_CONFIG


def publish_device_update_like_simulator(device, override_status=None, extra_payload=None):
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
        meta = load_device_metadata(device)
        if "temperature" in meta:
            payload["temperature"] = meta["temperature"]
        if device.target_temperature is not None:
            payload["target_temperature"] = device.target_temperature

    elif device.device_type == "actuator":
        # Mirror simulator: emit x,y,position if present in metadata (no movement here)
        meta = load_device_metadata(device)
        x = meta.get("x")
        y = meta.get("y")
        if x is not None and y is not None:
            payload["x"] = x
            payload["y"] = y
            payload["position"] = int(((x + y) / 2) * 10)

    elif device.device_type in {
        "dishwasher",
        "washing_machine",
        "dryer",
        "oven",
        "microwave",
        "kettle",
        "gas",
        "fridge",
        "tv",
    }:
        meta = load_device_metadata(device)
        if device.target_temperature is not None:
            payload["target_temperature"] = device.target_temperature
        if device.current_temperature is not None:
            payload["temperature"] = device.current_temperature
        if device.mode:
            payload["mode"] = device.mode
        if meta.get("cycle"):
            payload["cycle"] = meta["cycle"]
        if meta.get("cycle_progress") is not None:
            payload["cycle_progress"] = meta["cycle_progress"]
        payload["status"] = int(bool(device.status))
        timer = meta.get("timer")
        if timer:
            timer_status = timer.get("status")
            if timer_status:
                payload["timer_status"] = timer_status
            remaining = timer.get("remaining_seconds")
            if remaining is not None:
                payload["timer_remaining_seconds"] = remaining

    # For sensors and unknown types we just send the base fields (no random numbers)

    if device.power_rating_watts:
        payload["power_capacity_w"] = device.power_rating_watts
    payload["power_w"] = round(device.current_power_watts or 0, 2)

    if extra_payload:
        payload.update(extra_payload)

    mqtt_publish.single(
        topic,
        json.dumps(payload),
        hostname=MQTT_BROKER,
        port=MQTT_PORT,
        **MQTT_PUBLISH_KWARGS,
    )
