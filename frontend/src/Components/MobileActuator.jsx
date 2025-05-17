// src/components/MobileActuator.jsx
export default function MobileActuator({ topic, current = "0,0" }) {
    const [x, y] = current.split(",").map(Number);
  
    return (
      <div className="bg-[#161b22] p-4 rounded-2xl border border-green-500 relative h-64">
        <h3 className="text-green-400 font-semibold mb-2">Mobile Actuator</h3>
        <div className="relative w-full h-full border border-green-600">
          <div
            className="absolute w-6 h-6 bg-green-400 rounded-full animate-pulse"
            style={{
              left: `${Math.min(Math.max(x, 0), 100)}%`,
              top: `${Math.min(Math.max(y, 0), 100)}%`,
              transform: "translate(-50%, -50%)",
            }}
          />
        </div>
      </div>
    );
  }
  