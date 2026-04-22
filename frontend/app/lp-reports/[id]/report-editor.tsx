"use client";

import { useMemo, useState } from "react";

type StartupUpdatePreview = {
  id: number;
  startup_name?: string | null;
  period_label?: string | null;
  summary?: string | null;
  highlights?: string[] | null;
  risks?: string[] | null;
  asks?: string[] | null;
};

type ReportDetail = {
  id: number;
  vehicle_name?: string | null;
  report_period_label?: string | null;
  status?: string | null;
  summary_of_progress?: string | null;
  significant_developments?: string | null;
  startup_updates?: StartupUpdatePreview[] | null;
};

export function ReportEditor({ initialReport, apiBase }: { initialReport: ReportDetail; apiBase: string }) {
  const [summary, setSummary] = useState(initialReport.summary_of_progress || "");
  const [developments, setDevelopments] = useState(initialReport.significant_developments || "");
  const [status, setStatus] = useState(initialReport.status || "Draft");
  const [saving, setSaving] = useState(false);
  const updates = useMemo(() => initialReport.startup_updates || [], [initialReport.startup_updates]);

  async function onSave() {
    setSaving(true);
    try {
      const response = await fetch(`${apiBase}/api/lp-reports/${initialReport.id}/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          summary_of_progress: summary,
          significant_developments: developments,
          status,
        }),
      });
      if (!response.ok) {
        throw new Error(`Save failed (${response.status})`);
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <div style={{ marginBottom: 16, color: "#555" }}>
        <div><strong>Vehicle:</strong> {initialReport.vehicle_name || "—"}</div>
        <div><strong>Period:</strong> {initialReport.report_period_label || "—"}</div>
      </div>

      <section style={{ border: "1px solid #ddd", borderRadius: 8, padding: 16, marginBottom: 16 }}>
        <h2>Summary of Progress</h2>
        <textarea value={summary} onChange={(e) => setSummary(e.target.value)} rows={10} style={{ width: "100%" }} />
      </section>

      <section style={{ border: "1px solid #ddd", borderRadius: 8, padding: 16, marginBottom: 16 }}>
        <h2>Significant Developments</h2>
        <textarea value={developments} onChange={(e) => setDevelopments(e.target.value)} rows={10} style={{ width: "100%" }} />
      </section>

      <div style={{ marginBottom: 16 }}>
        <label>
          Status{" "}
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="Draft">Draft</option>
            <option value="Published">Published</option>
          </select>
        </label>
      </div>

      <button onClick={onSave} disabled={saving}>
        {saving ? "Saving..." : "Save"}
      </button>

      <section style={{ border: "1px solid #ddd", borderRadius: 8, padding: 16, marginTop: 24 }}>
        <h2>Underlying Startup Updates</h2>
        {updates.length === 0 ? (
          <p>No source updates available.</p>
        ) : (
          <ul style={{ paddingLeft: 18 }}>
            {updates.map((u) => (
              <li key={u.id} style={{ marginBottom: 12 }}>
                <strong>{u.startup_name || "Unknown Startup"}</strong>
                {u.summary ? <div style={{ marginTop: 4 }}>{u.summary}</div> : null}
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
