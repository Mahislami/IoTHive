export default function ThermostatControl({ topic, current, onChange }) {
    return (
      <div className="thermo-control">
        <span>{topic}</span>
        <input
          type="range"
          min="10"
          max="30"
          value={parseFloat(current) || 20}
          onChange={e => onChange(topic, e.target.value)}
        />
        <strong>{current || "--"}°C</strong>
      </div>
    );
  }
  