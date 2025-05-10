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

* `sensor` – Sends periodic numeric data
* `light` – Simulates ON/OFF status
* `thermostat` – Sends temperature settings
* `switch` – Sends toggle state
* `actuator` – Can be extended for control commands

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
