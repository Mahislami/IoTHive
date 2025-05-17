// src/components/LightSwitch.jsx
export default function LightSwitch({ topic, label, current, onToggle }) {
    const isOn = current === "on";
  
    return (
      <div className="bg-[#161b22] p-4 rounded-2xl border border-yellow-400 shadow-md flex items-center justify-between">
        <span className="text-yellow-300 font-semibold">{label}</span>
        <button
          onClick={() => onToggle(topic, isOn ? "off" : "on")}
          className={`px-4 py-2 rounded-xl font-bold transition-all ${
            isOn
              ? "bg-yellow-400 text-black shadow-yellow-400 shadow-md"
              : "bg-gray-700 text-gray-300"
          }`}
        >
          {isOn ? "ON" : "OFF"}
        </button>
      </div>
    );
  }
  