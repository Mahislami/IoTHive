from __future__ import annotations

"""
Lightweight recommendation generator.
Heuristics only; avoids touching other apps and does not require time-series data.
"""

from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple, Sequence

from django.db import transaction
from django.utils.translation import gettext_lazy as _

from .appliances import APPLIANCE_SPECS
from .models import AlarmRule, Device, Recommendation
from .utils import load_device_metadata


@dataclass
class RecInput:
    device: Device
    title: str
    message: str
    severity: str = "warn"
    confidence: float = 0.5
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    expected_state: Optional[bool] = None
    target_note: str = ""
    metric: Optional[str] = None


def _numeric_bounds(device: Device) -> Tuple[Optional[float], Optional[float]]:
    meta = load_device_metadata(device)
    if device.device_type == "thermostat":
        target = device.target_temperature or meta.get("temperature")
        if target is not None:
            return max(16.0, target - 3), min(30.0, target + 3)
        return 18.0, 28.0
    if device.device_type == "sensor":
        reading = meta.get("reading")
        if reading is not None:
            return float(reading) * 0.7, float(reading) * 1.3
        return 10.0, 90.0
    if device.device_type in APPLIANCE_SPECS:
        spec = APPLIANCE_SPECS.get(device.device_type, {})
        tr = spec.get("temp_range")
        if tr:
            low, high = tr
            return float(low), float(high)
    return None, None


def _expected_state(device: Device) -> Optional[bool]:
    if device.device_type in ("switch", "light", "actuator"):
        return bool(device.status)
    if device.device_type in APPLIANCE_SPECS:
        return bool(device.status)
    return None


def _build_rec_inputs(devices: Iterable[Device]) -> List[RecInput]:
    recs: List[RecInput] = []
    for d in devices:
        if d.device_type in ("sensor", "thermostat"):
            mn, mx = _numeric_bounds(d)
            recs.append(
                RecInput(
                    device=d,
                    title=_("Set %(device_type)s thresholds") % {"device_type": d.get_device_type_display()},
                    message=_("Based on current readings, apply tighter min/max bounds."),
                    confidence=0.5,
                    min_value=mn,
                    max_value=mx,
                    metric="temperature" if d.device_type == "thermostat" else "reading",
                    severity="warn",
                )
            )
            recs.append(
                RecInput(
                    device=d,
                    title=_("Add operator note for %(device)s") % {"device": d.name},
                    message=_("Document expected behavior so alerts are actionable."),
                    confidence=0.3,
                    severity="info",
                    target_note=_("Add context for on-call operators."),
                    metric=None,
                )
            )
        elif d.device_type in ("switch", "light", "actuator"):
            recs.append(
                RecInput(
                    device=d,
                    title=_("Expected state for %(device_type)s") % {"device_type": d.get_device_type_display()},
                    message=_("Lock the expected state to reduce noise."),
                    confidence=0.4,
                    expected_state=_expected_state(d),
                    metric="state",
                    severity="info",
                    target_note=_("Alert when state changes unexpectedly."),
                )
            )
            recs.append(
                RecInput(
                    device=d,
                    title=_("Off-hours alert for %(device)s") % {"device": d.name},
                    message=_("Notify if this device toggles outside scheduled hours."),
                    confidence=0.25,
                    expected_state=_expected_state(d),
                    metric="state",
                    severity="warn",
                    target_note=_("Unexpected toggle outside schedule."),
                )
            )
        elif d.device_type in APPLIANCE_SPECS:
            mn, mx = _numeric_bounds(d)
            note = "Use appliance spec temperature range." if mn is not None else ""
            if mn is not None or mx is not None:
                recs.append(
                    RecInput(
                        device=d,
                        title=_("%(device_type)s safety band") % {"device_type": d.get_device_type_display()},
                        message=_("Apply bounds to catch overheating or abnormal power draw."),
                        confidence=0.5,
                        min_value=mn,
                        max_value=mx,
                        target_note=_("Use appliance spec temperature range.") if note else "",
                        metric="temperature",
                        severity="warn",
                    )
                )
            recs.append(
                RecInput(
                    device=d,
                    title=_("Maintenance reminder for %(device)s") % {"device": d.name},
                    message=_("Add a note about filter cleaning or descale intervals."),
                    confidence=0.2,
                    severity="info",
                    target_note=_("Track maintenance actions alongside alarms."),
                    metric=None,
                )
            )
        else:
            recs.append(
                RecInput(
                    device=d,
                    title=_("Baseline rule for %(device)s") % {"device": d.name},
                    message=_("Add a default rule so alarms can be tuned later."),
                    confidence=0.3,
                    metric="temperature",
                    severity="info",
                )
            )
    return recs


@transaction.atomic
def upsert_recommendation(rec: RecInput) -> Recommendation:
    defaults = {
        "message": rec.message,
        "severity": rec.severity,
        "confidence": rec.confidence,
        "target_min_value": rec.min_value,
        "target_max_value": rec.max_value,
        "target_expected_state": rec.expected_state,
        "target_severity": rec.severity,
        "target_note": rec.target_note,
        "target_metric": rec.metric,
        "acknowledged": False,
        "implemented": False,
        "dismissed": False,
    }
    obj, created = Recommendation.objects.get_or_create(
        device=rec.device,
        title=rec.title,
        defaults=defaults,
    )
    if created:
        return obj
    changed_fields = []
    for field, value in defaults.items():
        current = getattr(obj, field)
        if current != value:
            setattr(obj, field, value)
            changed_fields.append(field)
    if obj.dismissed:
        obj.dismissed = False
        changed_fields.append("dismissed")
    if changed_fields:
        obj.save(update_fields=changed_fields)
    return obj


def build_heuristic_inputs(devices: Optional[Iterable[Device]] = None) -> List[RecInput]:
    qs = devices if devices is not None else Device.objects.all()
    return _build_rec_inputs(qs)


def generate_recommendations(devices: Optional[Iterable[Device]] = None,
                             extra_inputs: Optional[Sequence[RecInput]] = None) -> List[Recommendation]:
    qs = devices if devices is not None else Device.objects.all()
    rec_inputs = list(extra_inputs or [])
    rec_inputs.extend(_build_rec_inputs(qs))
    created_or_updated: List[Recommendation] = []
    for rec in rec_inputs:
        created_or_updated.append(upsert_recommendation(rec))
    return created_or_updated
