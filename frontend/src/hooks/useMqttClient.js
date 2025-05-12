import { useEffect, useState } from 'react';
import mqtt from 'mqtt';

export default function useMqttClient(topic) {
  const [messages, setMessages] = useState([]);

  useEffect(() => {
    const client = mqtt.connect('ws://localhost:9001'); // broker must support WebSocket

    client.on('connect', () => {
      console.log('Connected to MQTT broker');
      client.subscribe(topic);
    });

    client.on('message', (topic, message) => {
      setMessages(prev => [...prev, { topic, message: message.toString(), time: new Date() }]);
    });

    return () => {
      client.end();
    };
  }, [topic]);

  return messages;
}
