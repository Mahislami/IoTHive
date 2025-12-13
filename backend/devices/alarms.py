# your_app/services/alarms.py
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import AlarmRule, AlarmEvent, Device, MetricChoices
from .utils import load_device_metadata

NUMERIC_TYPES = {'sensor', 'thermostat'}
BOOLEAN_TYPES = {'switch', 'light', 'actuator'}

def _get_numeric_value(device: Device, field: str | None = None):
    try:
        # direct device fields for power/temperature fallbacks
        if field in ("power_w", "power", "power_watts") and device.current_power_watts is not None:
            return float(device.current_power_watts)
        if field in ("temperature", "temp", "value") and device.current_temperature is not None:
            return float(device.current_temperature)
        meta = load_device_metadata(device)
        keys = [field] if field else []
        keys.extend(["power_w", "power", "power_watts", "value", "reading", "temperature"])
        for key in keys:
            if key in meta and meta[key] is not None:
                return float(meta[key])
        if device.current_temperature is not None:
            return float(device.current_temperature)
    except (TypeError, ValueError):
        pass
    return None

def _get_boolean_state(device: Device):
    return bool(device.status)

def _clear_inactive_rule_events(device: Device):
    # If a rule has been disabled, clear any active events tied to it.
    inactive_events = device.alarm_events.filter(
        is_active=True,
        rule__isnull=False,
        rule__active=False,
    )
    if inactive_events.exists():
        inactive_events.update(is_active=False, cleared_at=timezone.now())

def evaluate_device_alarms(device: Device):
    """Evaluate the active rules for a single device and raise/clear events."""
    _clear_inactive_rule_events(device)
    rules = device.alarm_rules.filter(active=True)

    for rule in rules:
        fired = False
        msg = None
        observed = None

        metric = rule.metric or MetricChoices.TEMPERATURE

        if metric != MetricChoices.STATE or device.device_type in NUMERIC_TYPES:
            v = _get_numeric_value(device, field=rule.field)
            if v is None:
                continue
            observed = str(v)
            if rule.min_value is not None and v < rule.min_value:
                fired = True
                msg = _("%(device)s: value %(value)s below %(threshold)s") % {
                    "device": device.name,
                    "value": v,
                    "threshold": rule.min_value,
                }
            if rule.max_value is not None and v > rule.max_value:
                fired = True
                msg = _("%(device)s: value %(value)s above %(threshold)s") % {
                    "device": device.name,
                    "value": v,
                    "threshold": rule.max_value,
                }

        elif metric == MetricChoices.STATE or device.device_type in BOOLEAN_TYPES:
            if rule.expected_state is not None:
                s = _get_boolean_state(device)
                # Fire when the state matches the configured trigger
                if s == rule.expected_state:
                    fired = True
                    observed = 'on' if s else 'off'
                    msg = _("%(device)s: state is %(state)s") % {
                        "device": device.name,
                        "state": observed,
                    }
        else:
            continue

        active_qs = AlarmEvent.objects.filter(rule=rule, is_active=True)
        if fired:
            if active_qs.exists():
                for ev in active_qs:
                    ev.severity = rule.severity
                    ev.message = msg or f"{device.name}: alarm"
                    ev.observed_value = observed or ''
                    ev.save(update_fields=["severity", "message", "observed_value"])
            else:
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
