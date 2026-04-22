import type { Metadata } from "next";
import Link from "next/link";

type ApiLpReportListItem = {
  id: number;
  vehicle_name?: string | null;
  report_period_label?: string | null;
  status?: string | null;
  summary_of_progress?: string | null;
};

export const metadata: Metadata = {
  title: "LP Reports",
};

async function loadLpReports(): Promise<ApiLpReportListItem[]> {
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
  const response = await fetch(`${apiBase}/api/lp-reports/`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`);
  }
  return (await response.json()) as ApiLpReportListItem[];
}

export default async function LpReportsPage() {
  const reports = await loadLpReports();
  return (
    <main>
      <p>
        <Link href="/">← Portfolio</Link>
      </p>
      <h1>Quarterly LP Reports</h1>
      {reports.length === 0 ? (
        <p>No LP reports generated yet.</p>
      ) : (
        <ul style={{ paddingLeft: 18 }}>
          {reports.map((r) => (
            <li key={r.id} style={{ marginBottom: 12 }}>
              <Link href={`/lp-reports/${r.id}`}>{r.vehicle_name || "Vehicle"} — {r.report_period_label || "Unknown period"}</Link>
              {" · "}
              <strong>{r.status || "Draft"}</strong>
              {r.summary_of_progress ? <div style={{ color: "#555", marginTop: 4 }}>{r.summary_of_progress}</div> : null}
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
