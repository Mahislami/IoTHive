// src/components/Header.jsx
export default function Header() {
    return (
      <header className="text-center py-6">
        <h1 className="text-4xl font-extrabold text-cyan-400 tracking-wider animate-pulse">
          IoTHive<span className="text-pink-500">.AI</span>
        </h1>
        <p className="text-gray-400 mt-2 text-sm">
          Real-time IoT Device Monitoring & Control Dashboard
        </p>
      </header>
    );
  }
  