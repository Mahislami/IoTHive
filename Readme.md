# 🐝 IoTHive

**IoTHive** is a containerized IoT simulation platform built with Django, Celery, and MQTT. It allows developers and researchers to simulate IoT devices (like sensors, lights, thermostats, and switches), manage them through a RESTful API, and stream data using the MQTT protocol.

This project is ideal for experimenting with edge-device communication, predictive maintenance, and anomaly detection pipelines using real-time simulated data.

---

## 🚀 Features

* 🌐 **Django REST API** for device registration and management
* 📡 **MQTT (Mosquitto)** broker for device communication
* ♻ **Celery** for periodic device simulation and task scheduling
* 🐳 Fully **Dockerized** architecture
* 🔍 Supports **sensor data publishing**, **device control simulation**, and **topic-based MQTT communication**
* 🍳 Dedicated **Kitchen Appliance Studio** with schematic-guided forms, alarms, and MQTT controls
* ⚡ **Per-device power modeling** with dedicated Grafana dashboards

---

## ⚒️ Architecture

```
+----------------+        +---------------------+        +--------------------+
|  MQTT Clients  |<-----> |  Mosquitto Broker   |<-----> |   MQTT Subscribers |
| (Celery Tasks) |        |    (on Docker)      |        |    (Optional UI)   |
+----------------+        +---------------------+        +--------------------+
        |                               ↑
        | Celery Task                   |
        ↓                               |
+----------------+          +-------------------------+
| Django Backend |<-------->|     PostgreSQL / SQLite |
|  (REST API)    |          +-------------------------+
+----------------+
```

---

## 📦 Tech Stack

* **Backend**: Django, Django REST Framework
* **Task Queue**: Celery
* **Broker**: Redis
* **MQTT**: Mosquitto
* **Containers**: Docker, Docker Compose

---

## 🐳 Quick Start (Dockerized)

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/iothive.git
cd iothive
```

### 2. Build and Run the Services

```bash
docker-compose up --build
```

### 3. Run Initial Migrations

In a separate terminal:

```bash
docker-compose exec backend python manage.py migrate
```
```bash
% docker exec -it mqtt-client /bin/sh
/ # mosquitto_sub -h mosquitto-broker -p 1883 -t home/livingroom/#
```
```bash
docker exec -it iothive_backend_1 sh
python manage.py shell
from devices.tasks import simulate_device_activity
>>> simulate_device_activity.delay()
```

### 4. Seed Demo Data (Recommended)

Bootstrap demo users, kitchen appliances, standard devices, and alarm rules so the dashboards light up immediately:

```bash
docker-compose exec backend python manage.py seed_demo
```

This creates a demo administrator (`demo_admin` / `admin123`) that you can use to log in right away—be sure to change the password afterwards.

If you want fresh telemetry, start the Celery worker (step above) or trigger `simulate_device_activity` again once containers are running.
---

## 🔐 HTTPS Access

The stack now auto-generates a self-signed certificate in `certs/https` via the `https-certs-init` helper container. When you run `docker-compose up`, the script creates `iothive.crt` and `iothive.key`, mounts them into both **nginx** and **InfluxDB**, and forces the public endpoints through HTTPS on port `443`.

To avoid browser warnings, import `certs/https/iothive.crt` into your workstation's trust store (Keychain Access on macOS, certmgr on Windows, or `/usr/local/share/ca-certificates` on Linux). Once trusted, you can access:

* https://localhost/ for the Django backend
* https://grafana.localhost/ for Grafana (served from its own hostname)
* https://localhost/influxdb/ for the InfluxDB UI/API (Basic Auth + token)

Telegraf now communicates with InfluxDB over `https://influxdb:8086` and trusts the same certificate, so metrics continue to flow without disabling TLS verification.
---

## ⚙️ API Endpoints

| Method | Endpoint           | Description                 |
| ------ | ------------------ | --------------------------- |
| GET    | `/devices/`        | List all registered devices |
| POST   | `/devices/create/` | Register a new device       |

Sample POST body for device creation (use in Postman):

```json
{
  "name": "Temperature Sensor 1",
  "device_type": "sensor",
  "topic": "sensors/temperature"
}
```

---

## 📡 MQTT Topics

Each device has its own topic. Devices publish data to their respective topics using `paho-mqtt`. You can subscribe using:

```bash
mosquitto_sub -h localhost -t sensors/temperature
```

---

## 🔀 Simulating Device Activity

Device activity is triggered through **Celery**:

### Start Celery Worker

```bash
docker-compose exec celery celery -A iothive worker --loglevel=info
```

### Periodically Simulate Devices

Celery will pick up the `simulate_device_activity` task which simulates each device’s MQTT behavior based on its type.

---

## 📂 Project Structure

```
iothive/
├── backend/
│   ├── devices/              # Django app for device models & views
│   ├── tasks.py              # Celery tasks simulating devices
│   └── ...
├── docker-compose.yml
├── mosquitto/                # Mosquitto config
└── README.md
```

---

## 📌 Device Types Supported

* `sensor` – Sends periodic numeric data (0–1.5 W consumption)
* `light` – Simulates ON/OFF status with realistic draw
* `thermostat` – Sends ambient temperature readings
* `switch` – Sends toggle state
* `actuator` – Emits positional data for moving assets
* `dishwasher`, `washing_machine`, `dryer`, `oven`, `microwave`, `kettle`, `gas`, `fridge` – Smart appliances with realistic temperature/power curves that admins/operators can control via the dashboard

Each powered device now publishes an additional MQTT topic under `iot/power/<device_type>/<id>`. Telegraf subscribes to the `iot/#` namespace so Grafana can present a dedicated **Power Usage** board (link exposed on the dashboard). Use the new *Control* action on appliance rows to push on/off, mode, temperature, and cycle changes back through MQTT in real time.

---

## 🧰 Optional Services & Profiles

Docker Compose now respects profiles so you can slim down the stack:

* `monitoring` – InfluxDB, Telegraf, and Grafana (enabled by default via `.env`)
* `tools` – MQTT sample client container

The repository ships with a `.env` file that sets `COMPOSE_PROFILES=monitoring,tools`, so `docker-compose up --build` behaves exactly as before. To run a lighter stack, edit `.env` and remove the profiles you do not need, or invoke Compose with an explicit list:

```bash
COMPOSE_PROFILES=monitoring docker-compose up --build
```

This keeps the original workflow intact while making it easy to toggle optional components for headless deployments or CI.

---

## 💡 Use Cases

* Research on IoT communication models
* Testing predictive analytics pipelines
* Prototyping smart device dashboards
* Teaching MQTT/Django/Celery integration

---

## 🤖 Contributing

Pull requests are welcome! For major changes, please open an issue first to discuss what you would like to change.

---

## 📜 License

MIT License

---

## 🤛🏼 Author

Mahdi — built for academic research and smart systems prototyping.
