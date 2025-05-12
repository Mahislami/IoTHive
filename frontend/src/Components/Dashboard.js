import React from 'react';
import useMqttClient from '../hooks/useMqttClient';

export default function Dashboard() {
  const messages = useMqttClient('devices/#');

  return (
    <div>
      <h2>Live Device Data</h2>
      <ul>
        {messages.map((msg, idx) => (
          <li key={idx}>
            <strong>{msg.topic}</strong>: {msg.message} <em>({msg.time.toLocaleTimeString()})</em>
          </li>
        ))}
      </ul>
    </div>
  );
}