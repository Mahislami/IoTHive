from celery import shared_task
import random
import json
import paho.mqtt.publish as publish
from django.db.models import Exists, OuterRef
from django.utils import timezone

from .models import Device, AlarmRule, AlarmEvent
from .alarms import evaluate_device_alarms
from .utils import load_device_metadata, save_device_metadata
from .appliances import (
    APPLIANCE_SPECS,
    AMBIENT_TEMPERATURE,
    get_appliance_spec,
)
from .timers import supports_timer, update_timer_runtime
from .power import compute_appliance_draw

# --- MQTT config (same as before) ---
MQTT_BROKER = 'mosquitto-broker'
MQTT_PORT = 1883

# Actuator bounds
ROOM_WIDTH = 10
ROOM_HEIGHT = 10



def _rand_span(value):
    if isinstance(value, (list, tuple)):
        return random.uniform(value[0], value[1])
    return float(value)


def _persist_state(device, meta, extra_fields=None):
    extra_fields = extra_fields or []
    update_fields = set(extra_fields)
    update_fields.add("metadata")
    save_device_metadata(device, meta, update_fields=tuple(update_fields))


def _power_topic(device):
    return f"iot/power/{device.device_type}/{device.id}"


def _publish_power(device, extra=None):
    payload = {
        "device": device.name,
        "type": device.device_type,
        "power_w": round(device.current_power_watts or 0, 2),
        "power_capacity_w": device.power_rating_watts,
    }
    if device.target_temperature is not None:
        payload["target_temperature"] = device.target_temperature
    if device.current_temperature is not None:
        payload["temperature"] = device.current_temperature
    if device.mode:
        payload["mode"] = device.mode
    if extra:
        payload.update(extra)
    meta = load_device_metadata(device)
    if device.device_type in APPLIANCE_SPECS:
        _enrich_appliance_payload(payload, device, meta)
    _pub(_power_topic(device), payload)


def _enrich_appliance_payload(payload, device, meta):
    payload["status"] = int(bool(device.status))
    timer = (meta or {}).get("timer")
    if timer:
        timer_status = timer.get("status")
        if timer_status:
            payload["timer_status"] = timer_status
        remaining = timer.get("remaining_seconds")
        if remaining is not None:
            payload["timer_remaining_seconds"] = remaining


def _complete_timer(device, meta, spec):
    timer = meta.get("timer") or {}
    if timer.get("notified"):
        return
    timer["completed_at"] = timezone.now().isoformat()
    timer["status"] = "completed"
    timer["notified"] = True
    meta["timer"] = timer
    message = f"{device.name} timer finished"
    observed = f"{timer.get('duration_minutes')} min" if timer.get("duration_minutes") else ""
    event = AlarmEvent.objects.create(
        device=device,
        rule=None,
        message=message,
        severity="info",
        observed_value=observed,
    )
    timer["alarm_event_id"] = event.id
    if spec and spec.get("cycles"):
        meta["cycle_progress"] = 100
    device.status = False


def _handle_timer_meta(device, meta, spec):
    if not supports_timer(device.device_type):
        return
    timer = meta.get("timer")
    if not timer or timer.get("status") not in {"running", "completed"}:
        return
    timer, completed = update_timer_runtime(timer)
    meta["timer"] = timer
    if completed:
        _complete_timer(device, meta, spec)


def _initialize_appliance_state(device):
    spec = get_appliance_spec(device.device_type)
    if not spec:
        return
    meta = load_device_metadata(device)
    if not device.power_rating_watts:
        device.power_rating_watts = spec["power_rating"]
    if not device.mode:
        device.mode = spec["modes"][0]
    if spec.get("cycles"):
        meta.setdefault("cycle", spec["cycles"][0])
        meta.setdefault("cycle_progress", 0)
    if spec.get("temp_range"):
        low, high = spec["temp_range"]
        if device.target_temperature is None:
            device.target_temperature = round(random.uniform(low, high), 1)
        if device.current_temperature is None:
            offset = random.uniform(2, 6)
            if spec.get("heats", True):
                device.current_temperature = max(low, device.target_temperature - offset)
            else:
                device.current_temperature = min(high, device.target_temperature + offset)
    if device.device_type == "fridge":
        device.status = True  # fridges stay on
    base_idle = _rand_span(spec["idle"])
    adjusted = compute_appliance_draw(device, spec, base_idle, meta, bool(device.status))
    device.current_power_watts = round(adjusted, 2)
    _persist_state(
        device,
        meta,
        extra_fields=[
            "power_rating_watts",
            "mode",
            "target_temperature",
            "current_temperature",
            "current_power_watts",
            "status",
        ],
    )


def _tick_appliance(device):
    spec = get_appliance_spec(device.device_type)
    if not spec:
        return None, None
    meta = load_device_metadata(device)
    _handle_timer_meta(device, meta, spec)
    timer_state = meta.get("timer") or {}
    timer_completed = timer_state.get("status") == "completed"
    running = bool(device.status)
    if device.device_type == "fridge":
        running = True
    draw = _rand_span(spec["active"] if running else spec["idle"])
    draw = compute_appliance_draw(device, spec, draw, meta, running)

    if spec.get("temp_range"):
        target = device.target_temperature
        if target is None:
            low, high = spec["temp_range"]
            target = (low + high) / 2
            device.target_temperature = target
        current = device.current_temperature if device.current_temperature is not None else target
        if spec.get("heats", True):
            if running:
                current = min(target, current + random.uniform(0.8, 2.5))
            else:
                current = max(AMBIENT_TEMPERATURE, current - random.uniform(0.4, 1.0))
        else:
            if running:
                current = max(target, current - random.uniform(0.4, 1.2))
            else:
                current = min(AMBIENT_TEMPERATURE, current + random.uniform(0.3, 0.8))
        device.current_temperature = round(current, 1)

    if spec.get("cycles"):
        progress = meta.get("cycle_progress", 0)
        if timer_completed:
            progress = 100
        elif running:
            progress = min(100, progress + random.uniform(5, 18))
        else:
            progress = max(0, progress - random.uniform(4, 10))
        if progress >= 100 and device.device_type != "fridge" and not timer_completed:
            device.status = False
            progress = 0
        meta["cycle_progress"] = round(progress, 1)

    device.current_power_watts = round(draw, 2)
    _persist_state(
        device,
        meta,
        extra_fields=["current_power_watts", "current_temperature", "target_temperature", "status"],
    )
    return meta, draw

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
            meta = load_device_metadata(device)
            meta["reading"] = random.randint(20, 100)
            device.current_power_watts = round(random.uniform(0.5, 1.5), 2)
            save_device_metadata(device, meta, update_fields=("metadata", "current_power_watts"))
            payload["reading"] = meta["reading"]

        elif device.device_type == 'light':
            new_status = random.choice([0, 1])
            device.status = new_status
            device.current_power_watts = 9 if new_status else 0.4
            device.save(update_fields=["status", "current_power_watts"])
            payload["status"] = new_status

        elif device.device_type == 'switch':
            state = random.choice([0, 1])
            device.current_power_watts = 2 if state else 0.1
            device.status = state
            device.save(update_fields=["status", "current_power_watts"])
            payload["state"] = state

        elif device.device_type == 'thermostat':
            meta = load_device_metadata(device)
            temp = round(random.uniform(18.0, 25.0), 1)
            meta["temperature"] = temp
            device.current_power_watts = round(random.uniform(3, 8), 2)
            save_device_metadata(
                device,
                meta,
                update_fields=("metadata", "current_power_watts"),
            )
            payload["temperature"] = temp

        elif device.device_type == 'actuator':
            meta = load_device_metadata(device)
            if not meta:
                meta = {"x": random.randint(0, ROOM_WIDTH), "y": random.randint(0, ROOM_HEIGHT)}
            x = meta.get("x", 0)
            y = meta.get("y", 0)
            dx = random.choice([-1, 0, 1])
            dy = random.choice([-1, 0, 1])
            new_x = max(0, min(ROOM_WIDTH, x + dx))
            new_y = max(0, min(ROOM_HEIGHT, y + dy))
            meta.update({"x": new_x, "y": new_y})
            device.current_power_watts = round(random.uniform(1.5, 4.0), 2)
            save_device_metadata(device, meta, update_fields=("metadata", "current_power_watts"))
            payload.update({"x": new_x, "y": new_y, "position": int((new_x + new_y) / 2 * 10)})

        elif device.device_type in APPLIANCE_SPECS:
            if device.metadata is None:
                _initialize_appliance_state(device)
            meta, draw = _tick_appliance(device)
            meta = meta or load_device_metadata(device)
            payload.update({
                "power_w": round(device.current_power_watts, 2),
                "mode": device.mode,
            })
            if device.current_temperature is not None:
                payload["temperature"] = device.current_temperature
            if device.target_temperature is not None:
                payload["target_temperature"] = device.target_temperature
            if meta.get("cycle_progress") is not None:
                payload["cycle_progress"] = meta["cycle_progress"]
            if meta.get("cycle"):
                payload["cycle"] = meta["cycle"]
            _enrich_appliance_payload(payload, device, meta)

        else:
            payload["message"] = "Unknown device update"

        if "power_w" not in payload:
            payload["power_w"] = round(device.current_power_watts or 0, 2)

        _pub(topic, payload)
        if device.current_power_watts:
            _publish_power(device)
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
            meta = load_device_metadata(device)
            if "reading" not in meta:
                meta["reading"] = random.randint(20, 100)
            device.current_power_watts = round(random.uniform(0.4, 1.2), 2)
            save_device_metadata(device, meta, update_fields=("metadata", "current_power_watts"))
            payload["reading"] = meta["reading"]

        elif device.device_type == 'light':
            payload["status"] = int(bool(device.status))
            device.current_power_watts = 9 if device.status else 0.4
            device.save(update_fields=["current_power_watts"])

        elif device.device_type == 'switch':
            val = int(bool(getattr(device, "status", 0)))
            payload["state"] = val
            device.current_power_watts = 2 if val else 0.1
            device.save(update_fields=["current_power_watts"])

        elif device.device_type == 'thermostat':
            meta = load_device_metadata(device)
            if "temperature" not in meta:
                meta["temperature"] = round(random.uniform(19.0, 23.0), 1)
            device.current_power_watts = round(random.uniform(3, 8), 2)
            save_device_metadata(device, meta, update_fields=("metadata", "current_power_watts"))
            payload["temperature"] = meta["temperature"]

        elif device.device_type == 'actuator':
            meta = load_device_metadata(device)
            x = int(meta.get("x", 0))
            y = int(meta.get("y", 0))
            moving_right = bool(meta.get("moving_right", True))
            row_step = int(meta.get("row_step", 1))

            if moving_right:
                if x < ROOM_WIDTH:
                    x += 1
                else:
                    y = min(ROOM_HEIGHT, y + row_step)
                    moving_right = False
            else:
                if x > 0:
                    x -= 1
                else:
                    y = min(ROOM_HEIGHT, y + row_step)
                    moving_right = True

            if y >= ROOM_HEIGHT:
                y = ROOM_HEIGHT - 1

            meta.update({"x": x, "y": y, "moving_right": moving_right, "row_step": row_step})
            device.current_power_watts = round(random.uniform(1.5, 4.0), 2)
            save_device_metadata(device, meta, update_fields=("metadata", "current_power_watts"))

            payload.update({
                "x": x,
                "y": y,
                "position": int((x + y) / 2 * 10),
            })

        elif device.device_type in APPLIANCE_SPECS:
            _initialize_appliance_state(device)
            meta = load_device_metadata(device)
            spec = APPLIANCE_SPECS.get(device.device_type)
            _handle_timer_meta(device, meta, spec)
            payload.update({
                "power_w": round(device.current_power_watts, 2),
                "mode": device.mode,
            })
            if device.current_temperature is not None:
                payload["temperature"] = device.current_temperature
            if device.target_temperature is not None:
                payload["target_temperature"] = device.target_temperature
            if meta.get("cycle"):
                payload["cycle"] = meta["cycle"]
            if meta.get("cycle_progress") is not None:
                payload["cycle_progress"] = meta["cycle_progress"]
            _enrich_appliance_payload(payload, device, meta)

        else:
            payload["message"] = "Unknown device initial state"

        if "power_w" not in payload:
            payload["power_w"] = round(device.current_power_watts or 0, 2)

        _pub(topic, payload)
        if device.current_power_watts:
            _publish_power(device)
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
            meta = load_device_metadata(device)
            meta["reading"] = random.randint(20, 100)
            device.current_power_watts = round(random.uniform(0.5, 1.5), 2)
            save_device_metadata(device, meta, update_fields=("metadata", "current_power_watts"))
            payload["reading"] = meta["reading"]

        elif device.device_type == 'thermostat':
            meta = load_device_metadata(device)
            t = meta.get("temperature", round(random.uniform(19.0, 23.0), 1))
            drift = random.uniform(-0.3, 0.3)  # gentle drift
            new_t = max(16.0, min(28.0, round(t + drift, 1)))
            meta["temperature"] = new_t
            device.current_power_watts = round(random.uniform(3, 8), 2)
            save_device_metadata(device, meta, update_fields=("metadata", "current_power_watts"))
            payload["temperature"] = new_t

        elif device.device_type == 'actuator':
            meta = load_device_metadata(device)
            x = meta.get("x", random.randint(0, ROOM_WIDTH))
            y = meta.get("y", random.randint(0, ROOM_HEIGHT))
            dx = random.choice([-1, 0, 1])
            dy = random.choice([-1, 0, 1])
            new_x = max(0, min(ROOM_WIDTH, x + dx))
            new_y = max(0, min(ROOM_HEIGHT, y + dy))
            meta.update({"x": new_x, "y": new_y})
            device.current_power_watts = round(random.uniform(1.5, 4.0), 2)
            save_device_metadata(device, meta, update_fields=("metadata", "current_power_watts"))
            payload.update({
                "x": new_x,
                "y": new_y,
                "position": int((new_x + new_y) / 2 * 10),
            })

        elif device.device_type == 'light':
            # Publish current DB status every tick (0/1), don't modify it
            payload["status"] = int(bool(device.status))
            device.current_power_watts = 9 if device.status else 0.4
            device.save(update_fields=["current_power_watts"])

        elif device.device_type == 'switch':
            state = int(bool(getattr(device, "status", 0)))
            payload["state"] = state
            device.current_power_watts = 2 if state else 0.1
            device.save(update_fields=["current_power_watts"])

        elif device.device_type in APPLIANCE_SPECS:
            meta, draw = _tick_appliance(device)
            meta = meta or load_device_metadata(device)
            payload.update({
                "mode": device.mode,
                "power_w": round(device.current_power_watts, 2),
            })
            if device.current_temperature is not None:
                payload["temperature"] = device.current_temperature
            if device.target_temperature is not None:
                payload["target_temperature"] = device.target_temperature
            if meta.get("cycle"):
                payload["cycle"] = meta["cycle"]
            if meta.get("cycle_progress") is not None:
                payload["cycle_progress"] = meta["cycle_progress"]
            _enrich_appliance_payload(payload, device, meta)

        else:
            # Skip sensors/unknowns here (or include if you want)
            continue

        if "power_w" not in payload:
            payload["power_w"] = round(device.current_power_watts or 0, 2)

        _pub(topic, payload)
        if device.current_power_watts:
            _publish_power(device)
        print(f"[TICK] Published to {topic}: {payload}")

@shared_task(name="devices.evaluate_alarms_task", acks_late=True, time_limit=20, soft_time_limit=15)
def evaluate_alarms_task():
    """
    Evaluate all devices that have active rules.
    """
    _evaluate_all()

def _evaluate_all():
    active_rule_subq = AlarmRule.objects.filter(device_id=OuterRef('pk'), active=True)
    qs = (Device.objects
          .annotate(has_active_rule=Exists(active_rule_subq))
          .filter(has_active_rule=True)
          .order_by('id'))

    batch_size = 200
    start = 0
    while True:
        batch = list(qs[start:start+batch_size])
        if not batch:
            break
        for device in batch:
            evaluate_device_alarms(device)
        start += batch_size
