// src/components/MqttConsole.jsx
export default function MqttConsole({ messages }) {
    const entries = Object.entries(messages).slice(-10).reverse();
  
    return (
      <div className="bg-[#161b22] p-4 rounded-2xl border border-indigo-500 font-mono text-sm max-h-64 overflow-y-auto">
        <h3 className="text-indigo-400 font-semibold mb-2">MQTT Log Console</h3>
        <ul className="text-gray-300 space-y-1">
          {entries.map(([topic, msg], i) => (
            <li key={i}>
              <span className="text-indigo-300">{topic}:</span> <span className="text-white">{msg}</span>
            </li>
          ))}
        </ul>
      </div>
    );
  }
  