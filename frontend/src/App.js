import { useEffect, useState } from "react";
import mqtt from "mqtt";

function App() {
  const [devices, setDevices] = useState([]);
  const [messages, setMessages] = useState({});

  useEffect(() => {
    // Fetch devices from Django
    fetch("http://localhost:8000/devices/")
      .then(res => res.json())
      .then(data => setDevices(data));
  }, []);

  useEffect(() => {
    // Connect to Mosquitto broker via WebSocket
    const client = mqtt.connect("ws://localhost:9001");

    client.on("connect", () => {
      console.log("Connected to MQTT broker");

      // Subscribe to all device topics
      devices.forEach(device => {
        if (device.topic) {
          client.subscribe(device.topic);
        }
      });
    });

    client.on("message", (topic, payload) => {
      setMessages(prev => ({
        ...prev,
        [topic]: payload.toString(),
      }));
    });

    return () => {
      client.end();
    };
  }, [devices]);

  return (
    <div>
      <h1>IoTHive Devices</h1>
      <ul>
        {devices.map(device => (
          <li key={device.id}>
            {device.name} ({device.device_type}) —{" "}
            <strong>{messages[device.topic] || "No data yet"}</strong>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default App;
