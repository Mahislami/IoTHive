import {
    LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, Legend,
  } from "recharts";
  
  export default function SensorChart({ topic, history }) {
    return (
      <div className="chart-container">
        <h3>{topic}</h3>
        <LineChart width={500} height={300} data={history}>
          <CartesianGrid stroke="#eee" />
          <XAxis dataKey="timestamp" />
          <YAxis />
          <Tooltip />
          <Legend />
          <Line type="monotone" dataKey="value" stroke="#8884d8" />
        </LineChart>
      </div>
    );
  }
  