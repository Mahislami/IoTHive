# MQTT TLS Certificates

Mosquitto now requires TLS with mutual certificate authentication on both its native MQTT (8883) and WebSocket (9883) listeners. The broker expects certificates at `/mosquitto/certs/*.crt|*.key`, and clients must present a certificate signed by the same CA.

## Generating Certificates
Use the helper script to create a private CA, broker cert, and client certs (including one for Telegraf):

This repo now wires the script into Docker Compose via the `mqtt-certs-init` service, so running `docker compose up` will automatically call it (and re-run it harmlessly on subsequent starts). You can still invoke it manually when working outside Docker:

```bash
./mosquitto/certs/generate-certs.sh
```

Outputs:
- `ca.crt`, `ca.key` – certificate authority trusted by Mosquitto and every client.
- `server.crt`, `server.key` – presented by Mosquitto.
- `telegraf-client.crt`, `telegraf-client.key` – used by the Telegraf container.
- `client.crt`, `client.key` – generic client certificate for ad-hoc testing.
- Additional per-client certificates are easy to mint afterward:

  ```bash
  CLIENT_CN=my-sensor CLIENT_PREFIX=sensor-my ./mosquitto/certs/generate-certs.sh
  ```

  This reuses the existing CA and writes `sensor-my.crt` / `sensor-my.key` without regenerating anything else.

Keep the CA private key (`ca.key`) secret. Commit only this README and the script—actual certs/keys stay ignored via `.gitignore`.

## Distributing Certificates
1. **Mosquitto container** – already mounts `./mosquitto/certs` at `/mosquitto/certs`. Place `ca.crt`, `server.crt`, and `server.key` there.
2. **Telegraf** – the compose file mounts the same directory into `/etc/telegraf/certs`; Telegraf is configured to use the CA plus the `telegraf-client` cert/key.
3. **Other MQTT clients** – supply:
   - `ca.crt` for server verification.
   - A unique client cert/key pair signed by `ca.crt`. Either reuse `client.*` from the script or generate per-device certs (recommended). Store the cert/key in the client container/host and point the MQTT client to them.

If you need password or ACL enforcement, enable it in `mosquitto.conf`—because `use_identity_as_username true` is set, Mosquitto will treat the client certificate’s Common Name as the username, making it simple to write ACLs per device.

## Rotation
Re-run the script periodically or whenever a key is compromised. Update the running containers by copying the new files into `mosquitto/certs/` and restarting the affected services (`mosquitto`, `telegraf`, and any client pods/containers).

## Optional: ACLs from Certificate CNs
Because Mosquitto’s config sets `use_identity_as_username true`, each client’s certificate Common Name becomes the MQTT username. You can leverage that for fine-grained authorization:

1. Edit `mosquitto/config/acl` with entries such as:
   ```
   user telegraf
   topic readwrite iot/#

   user sensor-01
   topic write home/sensor-01/#
   topic read control/sensor-01/#
   ```
2. Mosquitto already references this file (`acl_file /mosquitto/config/acl`); restart the container after edits.

Only keep ACL entries for the certificate CNs you actually issue—unknown CNs will be denied.

## Automated Device Certificates & ACLs
Django now auto-provisions a unique certificate for each `Device` record and rewrites the ACL file so that every device CN has scoped permissions:

- On startup, `devices.apps.DevicesConfig` calls into `devices.mqtt_security.ensure_all_devices_configured()` to generate certs for any existing devices and refresh the ACL.
- On every device create/update/delete, signals call into `devices.mqtt_security` to generate or clean up the cert (via `generate-certs.sh`) and refresh `mosquitto/config/acl`.
- If you ever want to force a rebuild manually, run:

  ```bash
  docker compose run --rm backend python manage.py sync_mqtt_security
  ```

This guarantees that adding a new device immediately yields TLS-encrypted MQTT traffic and topic-level authorization, without manual steps.
