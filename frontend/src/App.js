// Tailwind must be installed and configured in your React app
// This is the new App.js layout with futuristic AI-style dashboard

import { useEffect, useState } from "react";
import mqtt from "mqtt";
import Header from "./components/Header";
import SensorCard from "./components/SensorCard";
import LightSwitch from "./components/LightSwitch";
import ThermostatSlider from "./components/ThermostatSlider";
import MobileActuator from "./components/MobileActuator";
import MqttConsole from "./components/MqttConsole";

function App() {
  const [devices, setDevices] = useState([]);
  const [messages, setMessages] = useState({});
  const [history, setHistory] = useState({});
  const [client, setClient] = useState(null);

  useEffect(() => {
    fetch("http://localhost:8000/devices/")
      .then(res => res.json())
      .then(data => setDevices(data));
  }, []);

  useEffect(() => {
    const mqttClient = mqtt.connect("ws://localhost:9001");
    setClient(mqttClient);

    mqttClient.on("connect", () => {
      devices.forEach(device => {
        if (device.topic) mqttClient.subscribe(device.topic);
      });
    });

    mqttClient.on("message", (topic, payload) => {
      const value = payload.toString();

      setMessages(prev => ({ ...prev, [topic]: value }));

      setHistory(prev => ({
        ...prev,
        [topic]: [...(prev[topic] || []).slice(-49), {
          timestamp: new Date().toLocaleTimeString(),
          value: parseFloat(value) || value,
        }]
      }));
    });

    return () => mqttClient.end();
  }, [devices]);

  const toggleLight = (topic, newStatus) => {
    if (client) client.publish(topic, newStatus);
  };

  const setTemperature = (topic, temp) => {
    if (client) client.publish(topic, temp.toString());
  };

  return (
    <div className="min-h-screen bg-[#0d1117] text-white font-mono px-6 py-4">
      <Header />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-8">
        <div className="col-span-2 space-y-6">
          <h2 className="text-xl font-semibold text-cyan-400">Sensors</h2>
          {devices.filter(d => d.device_type === "sensor").map(device => (
            <SensorCard key={device.id} device={device} history={history[device.topic] || []} />
          ))}
        </div>

        <div className="space-y-6">
          <h2 className="text-xl font-semibold text-pink-400">Controls</h2>
          {devices.filter(d => d.device_type === "light").map(device => (
            <LightSwitch
              key={device.id}
              topic={device.topic}
              label={device.name}
              current={messages[device.topic]}
              onToggle={toggleLight}
            />
          ))}

          {devices.filter(d => d.device_type === "thermostat").map(device => (
            <ThermostatSlider
              key={device.id}
              topic={device.topic}
              label={device.name}
              current={messages[device.topic]}
              onChange={setTemperature}
            />
          ))}
        </div>
      </div>

      <div className="mt-10 grid grid-cols-1 lg:grid-cols-2 gap-6">
        <MobileActuator topic="home/mobile/position" current={messages["home/mobile/position"]} />
        <MqttConsole messages={messages} />
      </div>
    </div>
  );
}

export default App;
