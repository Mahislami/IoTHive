from celery import shared_task
from datetime import timedelta
from .models import Device
import random
import json
import paho.mqtt.publish as publish
from django.db.models import Exists, OuterRef
from django.core.cache import cache
from .models import Device, AlarmRule
from .alarms import evaluate_device_alarms

# --- MQTT config (same as before) ---
MQTT_BROKER = 'mosquitto-broker'
MQTT_PORT = 1883

# Actuator bounds
ROOM_WIDTH = 10
ROOM_HEIGHT = 10

# Helpers -------------------------------------------------------------

def _safe_load_meta(device):
    """device.metadata may be a JSON string or None."""
    try:
        return json.loads(device.metadata) if device.metadata else {}
    except Exception:
        return {}

def _save_meta(device, meta, fields=("metadata",)):
    device.metadata = json.dumps(meta)
    device.save(update_fields=list(fields))

def _pub(topic, payload_dict):
    publish.single(topic, json.dumps(payload_dict), hostname=MQTT_BROKER, port=MQTT_PORT)

def _topic_for(device):
    return device.topic or f"iot/sensors/{device.device_type}/{device.id}"

# Legacy "full random" simulator (unchanged so you can still call it) -----

@shared_task
def simulate_device_activity():
    devices = Device.objects.all()
    for device in devices:
        topic = _topic_for(device)
        payload = {"device": device.name, "type": device.device_type}

        if device.device_type == 'sensor':
            payload["reading"] = random.randint(20, 100)

        elif device.device_type == 'light':
            new_status = random.choice([0, 1])
            device.status = new_status
            device.save(update_fields=["status"])
            payload["status"] = new_status

        elif device.device_type == 'switch':
            payload["state"] = random.choice([0, 1])

        elif device.device_type == 'thermostat':
            payload["temperature"] = round(random.uniform(18.0, 25.0), 1)

        elif device.device_type == 'actuator':
            meta = _safe_load_meta(device)
            if not meta:
                meta = {"x": random.randint(0, ROOM_WIDTH), "y": random.randint(0, ROOM_HEIGHT)}
            x = meta.get("x", 0)
            y = meta.get("y", 0)
            dx = random.choice([-1, 0, 1])
            dy = random.choice([-1, 0, 1])
            new_x = max(0, min(ROOM_WIDTH, x + dx))
            new_y = max(0, min(ROOM_HEIGHT, y + dy))
            meta.update({"x": new_x, "y": new_y})
            _save_meta(device, meta)
            payload.update({"x": new_x, "y": new_y, "position": int((new_x + new_y) / 2 * 10)})

        else:
            payload["message"] = "Unknown device update"

        _pub(topic, payload)
        print(f"[MQTT] Published to {topic}: {payload}")

# --------------------------------------------------------------------
# New flow you asked for:
#   1) initialize_device_state(): one-off, sets and publishes initial values.
#   2) tick_dynamic_devices(): every 10s, only thermostat + actuator update.
#      lights/switches DO NOT change unless your form changes them.
# --------------------------------------------------------------------

@shared_task
def initialize_device_state():
    """
    Run once to set initial values and publish them.
    - sensor: publish one initial reading (DB not changed)
    - light: publish current DB status (do NOT randomize/change DB)
    - switch: publish current DB status or default 0 (do NOT randomize/change DB)
    - thermostat: set an initial temperature in metadata and publish
    - actuator: set initial x,y in metadata and publish
    """
    devices = Device.objects.all()
    for device in devices:
        topic = _topic_for(device)
        payload = {"device": device.name, "type": device.device_type}

        if device.device_type == 'sensor':
            meta = _safe_load_meta(device)
            if "reading" not in meta:
                meta["reading"] = random.randint(20, 100)  # initial numeric metric
                _save_meta(device, meta)
            payload["reading"] = meta["reading"]

        elif device.device_type == 'light':
            # Keep whatever is in DB; do not randomize
            payload["status"] = int(bool(device.status))

        elif device.device_type == 'switch':
            # Keep DB truth; if your model lacks a field, default to 0
            # Assuming Device has .status; otherwise set to 0
            val = int(bool(getattr(device, "status", 0)))
            payload["state"] = val

        elif device.device_type == 'thermostat':
            meta = _safe_load_meta(device)
            # Initialize a starting temperature if not present
            if "temperature" not in meta:
                meta["temperature"] = round(random.uniform(19.0, 23.0), 1)
                _save_meta(device, meta)
            payload["temperature"] = meta["temperature"]

        elif device.device_type == 'actuator':
            meta = _safe_load_meta(device)
            x = int(meta.get("x", 0))
            y = int(meta.get("y", 0))
            moving_right = bool(meta.get("moving_right", True))
            row_step = int(meta.get("row_step", 1))

            # --- Lawnmower sweep update ---
            if moving_right:
            # Move right until right wall, then drop a row and reverse
                if x < ROOM_WIDTH:
                    x += 1
                else:
                # at right wall → go down a row, reverse direction
                    y = min(ROOM_HEIGHT, y + row_step)
                    moving_right = False
            else:
            # Move left until left wall, then drop a row and reverse
                if x > 0:
                    x -= 1
                else:
                    # at left wall → go down a row, reverse direction
                    y = min(ROOM_HEIGHT, y + row_step)
                    moving_right = True

            # Optional: when we reach bottom, wrap to top and continue sweeping
            if y >= ROOM_HEIGHT:
                y = y-1

            # Persist new state
            meta.update({"x": x, "y": y, "moving_right": moving_right, "row_step": row_step})
            _save_meta(device, meta)

            payload.update({
             "x": x,
            "y": y,
            "position": int((x + y) / 2 * 10),
            })

        else:
            payload["message"] = "Unknown device initial state"

        _pub(topic, payload)
        print(f"[INIT] Published to {topic}: {payload}")

@shared_task
def tick_dynamic_devices():
    """
    Run every 10 seconds.

    - thermostat: drift temperature slightly and publish (persist in metadata)
    - actuator: small movement and publish (persist in metadata)
    - light: DO NOT change DB; publish last known status each tick
    - switch: DO NOT change DB; publish last known state each tick

    Topics remain: device.topic OR f"iot/sensors/{device.device_type}/{device.id}"
    """
    devices = Device.objects.all()
    for device in devices:
        topic = device.topic or f"iot/sensors/{device.device_type}/{device.id}"
        payload = {"device": device.name, "type": device.device_type}

        if device.device_type == 'sensor':
            meta = _safe_load_meta(device)
            meta["reading"] = random.randint(20, 100)  # initial numeric metric
            _save_meta(device, meta)
            payload["reading"] = meta["reading"]

        elif device.device_type == 'thermostat':
            meta = _safe_load_meta(device)
            t = meta.get("temperature", round(random.uniform(19.0, 23.0), 1))
            drift = random.uniform(-0.3, 0.3)  # gentle drift
            new_t = max(16.0, min(28.0, round(t + drift, 1)))
            meta["temperature"] = new_t
            _save_meta(device, meta)
            payload["temperature"] = new_t

        elif device.device_type == 'actuator':
            meta = _safe_load_meta(device)
            x = meta.get("x", random.randint(0, ROOM_WIDTH))
            y = meta.get("y", random.randint(0, ROOM_HEIGHT))
            dx = random.choice([-1, 0, 1])
            dy = random.choice([-1, 0, 1])
            new_x = max(0, min(ROOM_WIDTH, x + dx))
            new_y = max(0, min(ROOM_HEIGHT, y + dy))
            meta.update({"x": new_x, "y": new_y})
            _save_meta(device, meta)
            payload.update({
                "x": new_x,
                "y": new_y,
                "position": int((new_x + new_y) / 2 * 10),
            })

        elif device.device_type == 'light':
            # Publish current DB status every tick (0/1), don't modify it
            payload["status"] = int(bool(device.status))

        elif device.device_type == 'switch':
            # Publish current DB state every tick (0/1), don't modify it
            # If you store switch state in `status`, this mirrors initialize_device_state()
            payload["state"] = int(bool(getattr(device, "status", 0)))

        else:
            # Skip sensors/unknowns here (or include if you want)
            continue

        _pub(topic, payload)
        print(f"[TICK] Published to {topic}: {payload}")

@shared_task
def evaluate_alarms_task():
    """
    Runs every 10 seconds. Evaluates only devices that have at least one active rule.
    Uses a short cache-based lock so tasks don't overlap if a previous run is slow.
    """
    # Optional lock (works best if you use django-redis as your CACHES backend)
    lock = getattr(cache, "lock", None)
    if lock:
        with cache.lock("alarms:evaluate", timeout=20, blocking_timeout=0):
            _evaluate_all()
    else:
        # Fallback without a lock
        _evaluate_all()


def _evaluate_all():
    # Prefilter to devices that *have* active rules (faster than iterating all)
    active_rule_subq = AlarmRule.objects.filter(device_id=OuterRef('pk'), active=True)
    qs = (Device.objects
          .annotate(has_active_rule=Exists(active_rule_subq))
          .filter(has_active_rule=True)
          .order_by('id'))

    # Iterate in chunks to keep memory small if you have many devices
    batch_size = 200
    start = 0
    while True:
        batch = list(qs[start:start+batch_size])
        if not batch:
            break
        for device in batch:
            # No DB transaction needed around the whole loop; the evaluator creates/clears events
            evaluate_device_alarms(device)
        start += batch_size