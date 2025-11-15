#!/bin/sh
set -eu

CERT_DIR=${CERT_DIR:-$(pwd)}
CERT_PATH="$CERT_DIR/iothive.crt"
KEY_PATH="$CERT_DIR/iothive.key"
DAYS=${TLS_CERT_DAYS:-825}
SUBJECT=${TLS_CERT_SUBJECT:-/CN=iothive.local}
SAN=${TLS_CERT_SAN:-DNS:localhost,DNS:iothive.local,DNS:influxdb,DNS:grafana.localhost,IP:127.0.0.1}

if [ -f "$CERT_PATH" ] && [ -f "$KEY_PATH" ]; then
  echo "TLS certificate already present, skipping generation"
  exit 0
fi

openssl req \
  -x509 \
  -nodes \
  -newkey rsa:4096 \
  -keyout "$KEY_PATH" \
  -out "$CERT_PATH" \
  -days "$DAYS" \
  -subj "$SUBJECT" \
  -addext "subjectAltName=$SAN"

echo "Self-signed TLS certificate created at $CERT_PATH"
