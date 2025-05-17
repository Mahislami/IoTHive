export default function LightControl({ topic, current, onToggle }) {
    return (
      <div className="light-control">
        <span>{topic}</span>
        <input
          type="checkbox"
          checked={current === "on"}
          onChange={() => onToggle(topic, current === "on" ? "off" : "on")}
        />
      </div>
    );
  }
  