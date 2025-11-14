#!/usr/bin/env bash
set -euo pipefail

CERT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$CERT_DIR"

DAYS="${CERT_DAYS:-3650}"
SERVER_CN="${SERVER_CN:-mosquitto-broker}"
SERVER_ALT_NAMES="${SERVER_ALT_NAMES:-DNS:mosquitto-broker,DNS:localhost,IP:127.0.0.1}"

sanitize_prefix() {
  echo "$1" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9_.-' '-'
}

generate_ca_and_server() {
  echo "Generating IoTHive MQTT CA..."
  openssl req -x509 -nodes -newkey rsa:4096 \
    -sha256 -days "$DAYS" \
    -keyout ca.key -out ca.crt \
    -subj "/CN=IoTHive MQTT CA"

  cat > server-ext.cnf <<EOF
subjectAltName=${SERVER_ALT_NAMES}
extendedKeyUsage=serverAuth
keyUsage=digitalSignature,keyEncipherment
EOF

  echo "Generating Mosquitto server certificate..."
  openssl req -nodes -newkey rsa:4096 \
    -keyout server.key -out server.csr \
    -subj "/CN=${SERVER_CN}"
  openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
    -out server.crt -days "$DAYS" -sha256 -extfile server-ext.cnf
  rm -f server.csr server-ext.cnf
}

generate_client_cert() {
  local cn="$1"
  local prefix="$2"
  local crt="${prefix}.crt"
  local key="${prefix}.key"

  if [[ -f "${crt}" || -f "${key}" ]]; then
    echo "Skipping ${cn} because ${crt} or ${key} already exist."
    return
  fi

  local ext_file
  local csr_file
  ext_file="$(mktemp client-ext.XXXXXX.cnf)"
  csr_file="$(mktemp client-csr.XXXXXX.csr)"

  cat > "${ext_file}" <<EOF
extendedKeyUsage=clientAuth
keyUsage=digitalSignature
EOF
  echo "Generating client certificate for ${cn} -> ${crt}"
  openssl req -nodes -newkey rsa:4096 \
    -keyout "${key}" -out "${csr_file}" \
    -subj "/CN=${cn}"
  openssl x509 -req -in "${csr_file}" -CA ca.crt -CAkey ca.key -CAcreateserial \
    -out "${crt}" -days "$DAYS" -sha256 -extfile "${ext_file}"
  rm -f "${csr_file}" "${ext_file}"
}

if [[ -n "${CLIENT_CN:-}" ]]; then
  if [[ ! -f ca.crt || ! -f ca.key ]]; then
    echo "CA not found. Run the script once without CLIENT_CN to bootstrap."
    exit 1
  fi
  safe_prefix="$(sanitize_prefix "${CLIENT_CN}")"
  prefix="${CLIENT_PREFIX:-${safe_prefix}}"
  generate_client_cert "${CLIENT_CN}" "${prefix}"
  echo "Client certificate for ${CLIENT_CN} written to ${prefix}.{crt,key}"
  exit 0
fi

if [[ ! -f ca.crt || ! -f ca.key ]]; then
  generate_ca_and_server
else
  echo "Existing CA detected; leaving ca.* and server.* untouched."
fi

generate_client_cert "${TELEGRAF_CN:-telegraf}" "telegraf-client"
generate_client_cert "${GENERIC_CN:-generic-mqtt-client}" "client"

echo "Done. Distribute ca.crt to every client and keep *.key files secure."
