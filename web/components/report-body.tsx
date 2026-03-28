import type { CSSProperties } from "react";

import { formatMetricValue } from "@/lib/format-metric";

const cardStyle: CSSProperties = {
  border: "1px solid #ddd",
  borderRadius: 8,
  padding: 16,
  margin: "18px 0",
};

const h2Style: CSSProperties = { color: "#16324f", marginBottom: 12 };

function labelize(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function MetricsTable({ metrics }: { metrics: Record<string, unknown> | null | undefined }) {
  if (!metrics || Object.keys(metrics).length === 0) {
    return <p style={{ color: "#555" }}>None</p>;
  }
  const entries = Object.entries(metrics);
  return (
    <table
      style={{
        width: "100%",
        borderCollapse: "collapse",
      }}
    >
      <tbody>
        {entries.map(([key, value]) => (
          <tr key={key}>
            <th
              style={{
                border: "1px solid #ddd",
                padding: 8,
                textAlign: "left",
                verticalAlign: "top",
                width: "32%",
                background: "#f7f7f7",
              }}
            >
              {labelize(key)}
            </th>
            <td
              style={{
                border: "1px solid #ddd",
                padding: 8,
                textAlign: "left",
                verticalAlign: "top",
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
              }}
            >
              {formatMetricValue(value)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function BulletList({ items }: { items: string[] | null | undefined }) {
  const cleaned = (items ?? []).filter((i) => i && i.trim());
  if (cleaned.length === 0) {
    return <p style={{ color: "#555" }}>None</p>;
  }
  return (
    <ul style={{ margin: "8px 0 0 1.1em", padding: 0 }}>
      {cleaned.map((i) => (
        <li key={i} style={{ marginBottom: 6 }}>
          {i}
        </li>
      ))}
    </ul>
  );
}

type ReportSectionsProps = {
  summary?: string | null;
  metrics?: Record<string, unknown> | null;
  highlights?: string[] | null;
  asks?: string[] | null;
  risks?: string[] | null;
};

export function ReportSections({ summary, metrics, highlights, asks, risks }: ReportSectionsProps) {
  const hasSummary = summary != null && String(summary).trim() !== "";
  const showMetrics = metrics != null && Object.keys(metrics).length > 0;

  return (
    <>
      <section style={cardStyle}>
        <h2 style={h2Style}>Summary</h2>
        {hasSummary ? <p style={{ whiteSpace: "pre-wrap" }}>{summary}</p> : <p style={{ color: "#555" }}>None</p>}
      </section>

      <section style={cardStyle}>
        <h2 style={h2Style}>Metrics</h2>
        {showMetrics ? <MetricsTable metrics={metrics} /> : <p style={{ color: "#555" }}>None</p>}
      </section>

      <section style={cardStyle}>
        <h2 style={h2Style}>Highlights</h2>
        <BulletList items={highlights} />
      </section>

      <section style={cardStyle}>
        <h2 style={h2Style}>Asks</h2>
        <BulletList items={asks} />
      </section>

      <section style={cardStyle}>
        <h2 style={h2Style}>Risks</h2>
        <BulletList items={risks} />
      </section>
    </>
  );
}
