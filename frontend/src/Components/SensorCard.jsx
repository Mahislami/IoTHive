// src/components/SensorCard.jsx
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

export default function SensorCard({ device, history }) {
  return (
    <div className="bg-[#161b22] p-4 rounded-2xl shadow-lg border border-cyan-600">
      <h3 className="text-cyan-300 font-semibold mb-2">{device.name}</h3>
      <ResponsiveContainer width="100%" height={150}>
        <LineChart data={history}>
          <XAxis dataKey="timestamp" hide />
          <YAxis domain={['auto', 'auto']} />
          <Tooltip />
          <Line type="monotone" dataKey="value" stroke="#0ff" dot={false} strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
