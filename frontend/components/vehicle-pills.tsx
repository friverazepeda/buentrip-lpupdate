type VehicleKind = "fund" | "spv" | "unknown";

function classifyVehicle(name: string): VehicleKind {
  const n = name.toLowerCase();
  if (n.includes("spv") || n.includes("series a") || n.includes("series b")) return "spv";
  if (n.includes("fund")) return "fund";
  return "unknown";
}

export function VehiclePills({ vehicles }: { vehicles: string[] }) {
  if (!vehicles?.length) {
    return <span style={{ fontSize: "0.92em", color: "#666" }}>No vehicles listed.</span>;
  }
  return (
    <>
      {vehicles.map((v) => {
        const kind = classifyVehicle(v);
        const bg = kind === "fund" ? "#e8f1ff" : kind === "spv" ? "#eef8ea" : "#f3f4f6";
        const color = kind === "fund" ? "#16324f" : kind === "spv" ? "#245c2a" : "#374151";
        return (
          <span
            key={v}
            style={{
              display: "inline-block",
              margin: "4px 8px 0 0",
              padding: "6px 10px",
              borderRadius: 999,
              fontSize: "0.92em",
              fontWeight: 600,
              background: bg,
              color,
            }}
          >
            {v}
          </span>
        );
      })}
    </>
  );
}
