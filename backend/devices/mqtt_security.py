import logging
import os
import subprocess
from pathlib import Path
from typing import Iterable, List, Sequence
from threading import Lock

from django.conf import settings

from .models import Device

logger = logging.getLogger(__name__)


CERTS_DIR = Path(settings.MQTT_CERTS_DIR)
ACL_PATH = Path(settings.MOSQUITTO_ACL_PATH)
GENERATE_SCRIPT = Path(settings.MQTT_CERT_GENERATE_SCRIPT)
DEVICE_CERT_PREFIX = settings.MQTT_DEVICE_CERT_PREFIX

BASE_ACL_RULES: Sequence = [
    ("telegraf", ["topic read iot/#", "topic read home/#"]),
    ("backend-service", ["topic write iot/#", "topic write home/#", "topic write iot/power/#"]),
    ("generic-mqtt-client", ["topic readwrite iot/#", "topic readwrite home/#"]),
]

ACL_HEADER = "# Managed by IoTHive – this file is auto-generated. Manual edits will be overwritten.\n"
_bootstrap_lock = Lock()
_bootstrapped = False


def device_certificate_cn(device: Device) -> str:
    return f"{DEVICE_CERT_PREFIX}-{device.id}"


def device_certificate_prefix(device: Device) -> str:
    # Keep filenames predictable; same as CN but safe for filesystem usage.
    return device_certificate_cn(device)


def ensure_device_security_assets(device: Device, *, resync_acl: bool = True) -> None:
    """
    Make sure a cert/key pair exists for the device and the ACL file references it.
    """
    if not device.pk:
        return
    try:
        _ensure_cert_exists(device)
        if resync_acl:
            sync_acl()
    except Exception:  # pragma: no cover - defensive logging
        logger.exception("Failed to provision MQTT credentials for device %s", device.id)


def remove_device_security_assets(device: Device, *, resync_acl: bool = True) -> None:
    """
    Remove device-specific certs and refresh ACLs after the device is deleted.
    """
    if not device.pk:
        return
    try:
        prefix = device_certificate_prefix(device)
        for suffix in (".crt", ".key"):
            path = CERTS_DIR / f"{prefix}{suffix}"
            if path.exists():
                path.unlink()
        if resync_acl:
            sync_acl()
    except Exception:  # pragma: no cover - defensive logging
        logger.exception("Failed to clean up MQTT credentials for device %s", device.id)


def sync_acl(*, devices: Iterable[Device] = None) -> None:
    """
    Rewrite the Mosquitto ACL file so it includes base service accounts and every device.
    """
    devices_qs = list(devices) if devices is not None else list(Device.objects.order_by("id"))
    lines: List[str] = [ACL_HEADER.rstrip(), ""]
    for username, rules in BASE_ACL_RULES:
        lines.append(f"user {username}")
        lines.extend(rules)
        lines.append("")
    for device in devices_qs:
        lines.extend(_device_acl_block(device))
    content = "\n".join(lines).rstrip() + "\n"
    ACL_PATH.parent.mkdir(parents=True, exist_ok=True)
    ACL_PATH.write_text(content, encoding="utf-8")
    logger.info("Mosquitto ACL updated at %s", ACL_PATH)


def _ensure_cert_exists(device: Device) -> None:
    cert_path = CERTS_DIR / f"{device_certificate_prefix(device)}.crt"
    key_path = CERTS_DIR / f"{device_certificate_prefix(device)}.key"
    if cert_path.exists() and key_path.exists():
        return
    if not GENERATE_SCRIPT.exists():
        logger.warning("Certificate generator script %s is missing", GENERATE_SCRIPT)
        return
    CERTS_DIR.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["CLIENT_CN"] = device_certificate_cn(device)
    env["CLIENT_PREFIX"] = device_certificate_prefix(device)
    try:
        subprocess.run([str(GENERATE_SCRIPT)], check=True, env=env)
        logger.info("Generated MQTT client cert for device %s", device.id)
    except subprocess.CalledProcessError:
        logger.exception("Failed to run %s for device %s", GENERATE_SCRIPT, device.id)


def _device_acl_block(device: Device) -> List[str]:
    lines: List[str] = [f"user {device_certificate_cn(device)}"]
    topic = (device.topic or "").strip()
    if topic:
        lines.append(f"topic readwrite {topic}")
        if not topic.endswith("#"):
            lines.append(f"topic readwrite {topic}/#")
    power_topic = f"iot/power/{device.device_type}/{device.id}"
    lines.append(f"topic write {power_topic}")
    lines.append("")
    return lines


def ensure_all_devices_configured() -> None:
    """
    Ensure every existing device has certificates and ACL entries.
    Safe to call multiple times; guarded by a lock to avoid redundant work.
    """
    global _bootstrapped
    if _bootstrapped:
        return
    with _bootstrap_lock:
        if _bootstrapped:
            return
        devices = list(Device.objects.order_by("id"))
        for device in devices:
            ensure_device_security_assets(device, resync_acl=False)
        sync_acl(devices=devices)
        _bootstrapped = True
