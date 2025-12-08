from __future__ import annotations

"""
Data-driven recommendations using a lightweight IsolationForest on recent InfluxDB data.
Falls back silently if data or client is unavailable.
"""

import os
import logging
from dataclasses import dataclass
from typing import Iterable, List, Optional

import numpy as np

try:
    from influxdb_client import InfluxDBClient
except ImportError:  # pragma: no cover - optional dependency
    InfluxDBClient = None

try:
    from sklearn.ensemble import IsolationForest
except ImportError:  # pragma: no cover - optional dependency
    IsolationForest = None

from .models import Device
from .recommendations import RecInput

logger = logging.getLogger(__name__)

# Defaults match docker-compose / telegraf settings
INFLUX_URL = os.environ.get("INFLUXDB_URL", "https://influxdb:8086")
INFLUX_TOKEN = os.environ.get("INFLUXDB_TOKEN", "iot_token")
INFLUX_ORG = os.environ.get("INFLUXDB_ORG", "iot_org")
INFLUX_BUCKET = os.environ.get("INFLUXDB_BUCKET", "iot_bucket")
INFLUX_VERIFY_SSL = os.environ.get("INFLUXDB_VERIFY_SSL", "false").lower() not in {"0", "false", "no"}

MAX_POINTS = int(os.environ.get("RECS_MAX_POINTS", "400"))
MIN_POINTS = 30


def _device_topic(device: Device) -> str:
    return device.topic or f"iot/sensors/{device.device_type}/{device.id}"


def _fetch_values(device: Device, fields=None) -> List[float]:
    if InfluxDBClient is None:
        return []
    fields = fields or ["temperature", "reading", "power_w"]
    topic = _device_topic(device)
    field_filter = " or ".join([f'r["_field"] == "{f}"' for f in fields])
    query = f"""
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: -72h)
  |> filter(fn: (r) => r["_measurement"] == "mqtt_consumer")
  |> filter(fn: (r) => r["topic"] == "{topic}")
  |> filter(fn: (r) => {field_filter})
  |> keep(columns: ["_value"])
  |> limit(n: {MAX_POINTS})
"""
    try:
        with InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG, verify_ssl=INFLUX_VERIFY_SSL) as client:
            tables = client.query_api().query(query)
        vals: List[float] = []
        for table in tables:
            for row in table.records:
                try:
                    vals.append(float(row["_value"]))
                except (TypeError, ValueError):
                    continue
        return vals
    except Exception:  # pragma: no cover - defensive
        logger.exception("Failed to fetch Influx data for device %s", device.id)
        return []


def _quantile_bounds(values: List[float], lower=5, upper=95) -> Optional[tuple]:
    if len(values) < MIN_POINTS:
        return None
    arr = np.array(values, dtype=float)
    return float(np.percentile(arr, lower)), float(np.percentile(arr, upper))


def _isolation_bounds(values: List[float]) -> Optional[tuple]:
    if IsolationForest is None or len(values) < MIN_POINTS:
        return None
    X = np.array(values, dtype=float).reshape(-1, 1)
    try:
        clf = IsolationForest(contamination=0.05, random_state=42)
        preds = clf.fit_predict(X)
        inliers = X[preds == 1].flatten()
        if len(inliers) < MIN_POINTS // 2:
            return None
        return float(np.percentile(inliers, 5)), float(np.percentile(inliers, 95))
    except Exception:  # pragma: no cover - defensive
        logger.exception("IsolationForest failed; falling back to quantiles")
        return _quantile_bounds(values)


def generate_ml_inputs(devices: Iterable[Device]) -> List[RecInput]:
    results: List[RecInput] = []
    for d in devices:
        vals = _fetch_values(d)
        bounds = _isolation_bounds(vals) if vals else None
        if not bounds:
            continue
        mn, mx = bounds
        title = f"Data-driven thresholds for {d.name}"
        msg = "Derived from recent telemetry (IsolationForest inliers p5–p95)."
        if d.device_type in ("thermostat",):
            metric = "temperature"
        elif d.device_type in ("sensor",):
            metric = "reading"
        elif d.device_type in ("switch", "light", "actuator"):
            metric = "state"
        elif d.device_type in ("fridge", "dishwasher", "washing_machine", "dryer", "oven", "microwave", "kettle", "gas", "tv"):
            metric = "power_w"
        else:
            metric = "reading"
        results.append(
            RecInput(
                device=d,
                title=title,
                message=msg,
                confidence=0.8,
                min_value=mn,
                max_value=mx,
                metric=metric,
                severity="warn",
            )
        )
    return results
