function formatNumber(n: number): string {
  if (!Number.isFinite(n)) return String(n);
  return Number.isInteger(n) ? `${n.toLocaleString("en-US")}` : `${n.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;
}

/**
 * Display helper for flexible metric values (mirrors Python reporting.fmt_metric_value shapes).
 */
export function formatMetricValue(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string" || typeof value === "boolean") return String(value);
  if (typeof value === "number") return formatNumber(value);
  if (Array.isArray(value)) return value.map((v) => String(v)).join(", ");
  if (typeof value === "object") {
    const o = value as Record<string, unknown>;
    if ("value" in o) {
      const raw = o.value;
      let base =
        typeof raw === "number" ? formatNumber(raw) : raw === null || raw === undefined ? "" : String(raw);
      if (o.currency === "USD") base = `$${base}`;
      if (typeof o.period === "string" && o.period) base += ` (${o.period})`;
      return base;
    }
    if ("low" in o && "high" in o) {
      const fmt = (x: unknown) =>
        typeof x === "number" ? formatNumber(x) : x === null || x === undefined ? "" : String(x);
      let low = fmt(o.low);
      let high = fmt(o.high);
      if (o.currency === "USD") {
        low = `$${low}`;
        high = `$${high}`;
      }
      return `${low} – ${high}`;
    }
    if ("previous_value" in o && "current_value" in o) {
      const fmt = (x: unknown) =>
        typeof x === "number" ? formatNumber(x) : x === null || x === undefined ? "" : String(x);
      let prev = fmt(o.previous_value);
      let curr = fmt(o.current_value);
      if (o.currency === "USD") {
        prev = `$${prev}`;
        curr = `$${curr}`;
      }
      return `${prev} → ${curr}`;
    }
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  return String(value);
}
