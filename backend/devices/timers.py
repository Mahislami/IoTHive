from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Optional, Tuple

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .appliances import APPLIANCE_SPECS


# All managed appliances support timers; some expose it as optional UX.
TIMER_DEVICE_TYPES = set(APPLIANCE_SPECS.keys())
OPTIONAL_TIMER_DEVICE_TYPES = {"tv", "gas"}


@dataclass
class TimerState:
    duration_minutes: int
    started_at: str
    expires_at: str
    remaining_seconds: int
    status: str = "running"
    progress_percent: float = 0.0
    notified: bool = False

    def as_dict(self) -> dict:
        return {
            "duration_minutes": self.duration_minutes,
            "started_at": self.started_at,
            "expires_at": self.expires_at,
            "remaining_seconds": self.remaining_seconds,
            "status": self.status,
            "progress_percent": self.progress_percent,
            "notified": self.notified,
        }


def supports_timer(device_type: str) -> bool:
    return device_type in TIMER_DEVICE_TYPES


def timer_optional(device_type: str) -> bool:
    return device_type in OPTIONAL_TIMER_DEVICE_TYPES


def start_timer(duration_minutes: int, now=None) -> dict:
    now = now or timezone.now()
    duration_minutes = max(1, int(duration_minutes))
    expires = now + timedelta(minutes=duration_minutes)
    return TimerState(
        duration_minutes=duration_minutes,
        started_at=now.isoformat(),
        expires_at=expires.isoformat(),
        remaining_seconds=duration_minutes * 60,
    ).as_dict()


def _parse_dt(value: Optional[str]):
    if not value:
        return None
    dt = parse_datetime(value)
    if dt and timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    return dt


def update_timer_runtime(timer_meta: dict, now=None) -> Tuple[dict, bool]:
    """
    Refresh remaining seconds/progress for a timer blob and report completion.
    """
    now = now or timezone.now()
    duration_minutes = int(timer_meta.get("duration_minutes") or 0)
    duration_seconds = max(60, duration_minutes * 60) if duration_minutes else None

    expires_at = _parse_dt(timer_meta.get("expires_at"))
    if expires_at:
        remaining = max(0, int((expires_at - now).total_seconds()))
    else:
        remaining = int(max(0, timer_meta.get("remaining_seconds", duration_seconds or 0)))

    timer_meta["remaining_seconds"] = remaining

    if duration_seconds:
        elapsed = duration_seconds - remaining
        timer_meta["progress_percent"] = round(min(100.0, max(0.0, (elapsed / duration_seconds) * 100)), 1)
    else:
        timer_meta["progress_percent"] = 0.0

    completed = remaining <= 0
    if completed:
        timer_meta["status"] = "completed"
    else:
        timer_meta["status"] = timer_meta.get("status") or "running"

    return timer_meta, completed
