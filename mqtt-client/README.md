# MQTT Test Client (TLS)

The `client` service in `docker-compose.yml` launches an interactive container with Mosquitto CLI tools preinstalled. It now mounts the TLS material generated under `mosquitto/certs/` at `/certs` so you can publish/subscribe over TLS:

```bash
# Shell into the client container
docker compose run --rm client sh

# Inside the container, publish with mutual TLS
mosquitto_pub -h mosquitto-broker -p 8883 \
  --cafile /certs/ca.crt \
  --cert /certs/client.crt \
  --key /certs/client.key \
  -t "iot/test" -m '{"value":42}' -d --tls-version tlsv1.2

# Subscribe similarly
mosquitto_sub -h mosquitto-broker -p 8883 \
  --cafile /certs/ca.crt \
  --cert /certs/client.crt \
  --key /certs/client.key \
  -t "iot/#" -v
```

For other MQTT devices/services, copy `ca.crt` plus create a unique client cert/key (rerun `generate-certs.sh` with `CLIENT_CN=<device>`). Configure your client library to use `ssl://<your-host>:8883` (or `wss://<your-host>:9883` for WebSockets) with that cert pair. The broker uses the client certificate CN as the MQTT username, making ACLs easy to manage.

> Tip: avoid reusing `client.crt` in production; mint per-device certs (e.g., `CLIENT_CN=sensor-01`) so Mosquitto ACLs can differentiate publishers.
