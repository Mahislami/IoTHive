# your_app/services/alarms.py
from .models import AlarmRule, AlarmEvent, Device

NUMERIC_TYPES = {'sensor', 'thermostat'}
BOOLEAN_TYPES = {'switch', 'light', 'actuator'}

def _get_numeric_value(device: Device):
    try:
        meta = device.metadata or {}
        if 'value' in meta and meta['value'] is not None:
            return float(meta['value'])
    except (TypeError, ValueError):
        pass
    return None

def _get_boolean_state(device: Device):
    return bool(device.status)

def evaluate_device_alarms(device: Device):
    """Evaluate the active rules for a single device and raise/clear events."""
    rules = device.alarm_rules.filter(active=True)

    for rule in rules:
        fired = False
        msg = None
        observed = None

        if device.device_type in NUMERIC_TYPES:
            v = _get_numeric_value(device)
            if v is None:
                continue
            observed = str(v)
            if rule.min_value is not None and v < rule.min_value:
                fired, msg = True, f"{device.name}: value {v} below {rule.min_value}"
            if rule.max_value is not None and v > rule.max_value:
                fired, msg = True, f"{device.name}: value {v} above {rule.max_value}"

        elif device.device_type in BOOLEAN_TYPES:
            if rule.expected_state is not None:
                s = _get_boolean_state(device)
                if s == rule.expected_state:
                    fired = True
                    observed = 'on' if s else 'off'
                    msg = f"{device.name}: state is {observed}"

        active_qs = AlarmEvent.objects.filter(rule=rule, is_active=True)
        if fired:
            if not active_qs.exists():
                AlarmEvent.objects.create(
                    device=device,
                    rule=rule,
                    message=msg or f"{device.name}: alarm",
                    severity=rule.severity,
                    observed_value=observed or '',
                )
        else:
            for ev in active_qs:
                ev.clear()
