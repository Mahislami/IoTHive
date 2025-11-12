from __future__ import annotations

from typing import Any, Dict

MODE_POWER_FACTORS: Dict[str, Dict[str, float]] = {
    "dishwasher": {"eco": 0.82, "normal": 1.0, "intense": 1.18},
    "washing_machine": {"cold": 0.85, "warm": 1.0, "hot": 1.2},
    "dryer": {"gentle": 0.88, "normal": 1.0, "boost": 1.22},
    "oven": {"bake": 1.0, "broil": 1.12, "fan": 0.92},
    "microwave": {"defrost": 0.7, "medium": 1.0, "high": 1.25},
    "kettle": {"keep-warm": 0.45, "boil": 1.0},
    "gas": {"simmer": 0.6, "medium": 1.0, "high": 1.2},
    "fridge": {"normal": 1.0, "boost": 1.18, "vacation": 0.65},
    "tv": {"cinema": 0.85, "standard": 1.0, "game": 1.05, "vivid": 1.18},
}

CYCLE_POWER_FACTORS: Dict[str, Dict[str, float]] = {
    "dishwasher": {"rinse": 0.65, "wash": 1.0, "dry": 0.85},
    "washing_machine": {"prewash": 0.7, "wash": 1.0, "spin": 0.9},
    "dryer": {"dry": 1.0, "cooldown": 0.6},
}


def _avg(value: Any) -> float:
    if isinstance(value, (tuple, list)):
        return sum(float(v) for v in value) / len(value)
    return float(value or 0)


def _number(meta: Dict[str, Any], key: str, default: float) -> float:
    raw = meta.get(key, default)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return float(default)


def _per_device_factor(device, meta: Dict[str, Any], running: bool) -> float:
    dtype = device.device_type
    factor = 1.0

    if dtype == "dishwasher":
        liters = _number(meta, "water_usage_l", 18)
        racks = _number(meta, "rack_count", 2)
        factor *= 0.75 + min(liters / 30.0, 1.0) * 0.4
        factor *= 0.9 + racks * 0.05
        if meta.get("sanitize_enabled"):
            factor *= 1.08

    elif dtype == "washing_machine":
        spin = _number(meta, "spin_speed_rpm", 800)
        capacity = _number(meta, "drum_capacity_kg", 6)
        factor *= 0.8 + min(spin / 1600.0, 1.2) * 0.4
        factor *= 0.85 + min(capacity / 10.0, 1.1) * 0.3

    elif dtype == "dryer":
        capacity = _number(meta, "drum_capacity_kg", 6)
        factor *= 0.85 + min(capacity / 10.0, 1.1) * 0.3
        if meta.get("has_heat_pump"):
            factor *= 0.88

    elif dtype == "oven":
        max_temp = _number(meta, "max_temperature_c", 250)
        if device.target_temperature:
            factor *= 0.7 + min(device.target_temperature / max_temp, 1.25) * 0.6

    elif dtype == "microwave":
        magnetron = _number(meta, "magnetron_watts", 1000)
        factor *= 0.75 + min(magnetron / 1800.0, 1.0) * 0.4

    elif dtype == "kettle":
        capacity = _number(meta, "capacity_liters", 1.2)
        factor *= 0.8 + min(capacity / 2.5, 1.0) * 0.4
        keep_warm = _number(meta, "keep_warm_minutes", 0)
        if not running and keep_warm:
            factor *= 0.7 + min(keep_warm / 60.0, 1.0) * 0.4

    elif dtype == "gas":
        burners = _number(meta, "burner_count", 4)
        factor *= 0.7 + min(burners / 6.0, 1.0) * 0.4

    elif dtype == "fridge":
        volume = _number(meta, "volume_liters", 300)
        factor *= 0.8 + min(volume / 600.0, 1.1) * 0.35
        if meta.get("has_ice_maker"):
            factor *= 1.05

    elif dtype == "tv":
        brightness = _number(meta, "current_brightness", _number(meta, "default_brightness", 55))
        volume = _number(meta, "current_volume", _number(meta, "default_volume", 20))
        screen = _number(meta, "screen_size_in", 55)
        factor *= 0.75 + (brightness / 100.0) * 0.4
        factor *= 0.8 + (volume / 100.0) * 0.25
        factor *= 0.8 + min(screen / 85.0, 1.2) * 0.3

    return max(factor, 0.1)


def compute_appliance_draw(device, spec, base_draw: float, meta: Dict[str, Any], running: bool) -> float:
    factor = 1.0

    mode_map = MODE_POWER_FACTORS.get(device.device_type)
    if mode_map:
        mode_key = (device.mode or "").lower()
        factor *= mode_map.get(mode_key, 1.0)

    cycle_map = CYCLE_POWER_FACTORS.get(device.device_type)
    if cycle_map:
        cycle_value = meta.get("cycle") or ""
        cycle_key = cycle_value.lower() if isinstance(cycle_value, str) else ""
        factor *= cycle_map.get(cycle_key, 1.0)

    progress = meta.get("cycle_progress")
    if isinstance(progress, (int, float)) and running:
        factor *= 0.7 + min(max(progress, 0), 100) / 100.0 * 0.5

    if spec.get("temp_range") and device.target_temperature is not None:
        current_temp = device.current_temperature
        if current_temp is None:
            current_temp = _number(meta, "temperature", device.target_temperature)
        delta = abs(device.target_temperature - current_temp)
        factor *= 1 + min(delta / 25.0, 0.5)

    factor *= _per_device_factor(device, meta, running)

    active_avg = _avg(spec.get("active", base_draw))
    idle_avg = _avg(spec.get("idle", base_draw))
    min_allowed = idle_avg * (0.6 if running else 0.4)
    max_allowed = max(active_avg, spec.get("power_rating", active_avg)) * 1.25

    adjusted = base_draw * factor
    return max(min_allowed, min(adjusted, max_allowed))
