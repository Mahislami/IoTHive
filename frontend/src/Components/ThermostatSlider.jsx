// src/components/ThermostatSlider.jsx
export default function ThermostatSlider({ topic, label, current = 20, onChange }) {
    return (
      <div className="bg-[#161b22] p-4 rounded-2xl border border-pink-500">
        <div className="flex justify-between items-center mb-2">
          <span className="text-pink-400 font-semibold">{label}</span>
          <span className="text-white font-mono text-lg">{current}°C</span>
        </div>
        <input
          type="range"
          min="10"
          max="35"
          step="0.5"
          value={parseFloat(current)}
          onChange={(e) => onChange(topic, e.target.value)}
          className="w-full accent-pink-400 cursor-pointer"
        />
      </div>
    );
  }
  