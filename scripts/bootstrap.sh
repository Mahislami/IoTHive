#!/usr/bin/env bash
set -euo pipefail

COMPOSE_CMD=${COMPOSE_CMD:-docker compose}
ACL_FILE="mosquitto/config/acl"

echo "==> Regenerating MQTT certs and ACL..."
$COMPOSE_CMD run --rm mqtt-certs-init

echo "==> Verifying ACL contains backend-service rules..."
if ! grep -q "^user backend-service" "$ACL_FILE"; then
  echo "ERROR: backend-service entry missing in $ACL_FILE" >&2
  exit 1
fi

echo "==> Bringing up the stack..."
$COMPOSE_CMD up -d
