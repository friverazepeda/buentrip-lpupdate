import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { ReportSections } from "@/components/report-body";
import { VehiclePills } from "@/components/vehicle-pills";
import type { ReportMeta } from "@/lib/types";

type PageProps = { params: Promise<{ slug: string; reportId: string }> };

const META_FIRST = ["report_period_label", "received_at", "subject", "gmail_message_id"] as const;

type ApiReportMetric = {
  name: string;
  value: string;
  change?: string | null;
};

type ApiReport = {
  id: number;
  startup_id?: number | null;
  startup_name?: string | null;
  vehicle_id?: number | null;
  vehicle_name?: string | null;
  period_label?: string | null;
  quarter?: string | null;
  year?: number | null;
  received_at?: string | null;
  highlights?: string | null;
  opportunities_and_challenges?: string | null;
  metrics?: ApiReportMetric[] | null;
  fundraising_updates?: string | null;
  asks?: string | null;
  risks?: string | null;
  
};

type PageReport = {
  startup: { slug: string; name: string };
  vehicles: string[];
  meta: ReportMeta;
  summary?: string | null;
  metrics?: Record<string, unknown> | null;
  highlights?: string[] | null;
  asks?: string[] | null;
  risks?: string[] | null;
};

function toLines(value?: string | null): string[] | null {
  if (!value) return null;
  const lines = value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  return lines.length > 0 ? lines : null;
}

function toMetricsMap(metrics?: ApiReportMetric[] | null): Record<string, unknown> | null {
  if (!metrics || metrics.length === 0) return null;
  const mapped: Record<string, unknown> = {};
  for (const metric of metrics) {
    const key = metric.name?.trim() || `Metric ${Object.keys(mapped).length + 1}`;
    mapped[key] = metric.change ? `${metric.value} (${metric.change})` : metric.value;
  }
  return Object.keys(mapped).length > 0 ? mapped : null;
}

async function loadReportById(slug: string, reportId: string): Promise<PageReport | null> {
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
  const response = await fetch(`${apiBase}/api/reports/${reportId}/`, { cache: "no-store" });
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`);
  }

  const raw = (await response.json()) as ApiReport;
  const startupName = raw.startup_name || "Startup";
  const vehicles = raw.vehicle_name ? [raw.vehicle_name] : [];

  const summaryParts = [raw.opportunities_and_challenges, raw.fundraising_updates]
    .filter((part): part is string => Boolean(part && part.trim()))
    .join("\n\n");

  const meta: ReportMeta = {
    report_period_label: raw.period_label,
    received_at: raw.received_at,
    startup_id: raw.startup_id,
    vehicle_id: raw.vehicle_id,
    vehicle_name: raw.vehicle_name,
    quarter: raw.quarter,
    year: raw.year,
  };

  return {
    startup: { slug, name: startupName },
    vehicles,
    meta,
    summary: summaryParts || null,
    metrics: toMetricsMap(raw.metrics),
    highlights: toLines(raw.highlights),
    asks: toLines(raw.asks),
    risks: toLines(raw.risks),
  };
}

function MetaTable({ meta }: { meta: ReportMeta }) {
  const rest = Object.keys(meta).filter((k) => !(META_FIRST as readonly string[]).includes(k));
  const ordered = [...META_FIRST.filter((k) => k in meta && meta[k] != null && String(meta[k]).trim() !== "")];
  const extra = rest
    .filter((k) => meta[k] != null && String(meta[k]).trim() !== "")
    .sort((a, b) => a.localeCompare(b));

  const rows: { key: string; label: string; value: string }[] = [];

  const push = (key: string) => {
    const raw = meta[key];
    if (raw === null || raw === undefined) return;
    const value = typeof raw === "object" ? JSON.stringify(raw) : String(raw);
    if (!value.trim()) return;
    rows.push({
      key,
      label: key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      value,
    });
  };

  ordered.forEach(push);
  extra.forEach(push);

  if (rows.length === 0) {
    return <p style={{ color: "#555" }}>None</p>;
  }

  return (
    <table className="data-table">
      <tbody>
        {rows.map((r) => (
          <tr key={r.key}>
            <th style={{ width: "28%" }}>{r.label}</th>
            <td style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>{r.value}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug, reportId } = await params;
  try {
    const r = await loadReportById(slug, reportId);
    if (!r) {
      return { title: "Report" };
    }
    const period = r.meta.report_period_label ?? reportId;
    return { title: `${r.startup.name} — ${period}` };
  } catch {
    return { title: "Report" };
  }
}

export default async function ReportPage({ params }: PageProps) {
  const { slug, reportId } = await params;
  let report: PageReport | null;
  try {
    report = await loadReportById(slug, reportId);
  } catch {
    notFound();
  }
  if (!report) {
    notFound();
  }

  return (
    <main id="lp-report-export">
      <p>
        <Link href="/">← Portfolio</Link>
        {" · "}
        <Link href={`/startups/${report.startup.slug}/`}>← {report.startup.name}</Link>
      </p>

      <h1>
        {report.startup.name}
        {report.meta.report_period_label ? ` — ${report.meta.report_period_label}` : ""}
      </h1>

      <div style={{ color: "#555", marginBottom: 16 }}>
        <strong>Vehicles:</strong> <VehiclePills vehicles={report.vehicles} />
      </div>

      <section
        style={{
          border: "1px solid #ddd",
          borderRadius: 8,
          padding: 16,
          margin: "18px 0",
        }}
      >
        <h2 style={{ color: "#16324f", marginBottom: 12 }}>Metadata</h2>
        <MetaTable meta={report.meta} />
      </section>

      <ReportSections
        summary={report.summary}
        metrics={report.metrics ?? undefined}
        highlights={report.highlights ?? undefined}
        asks={report.asks ?? undefined}
        risks={report.risks ?? undefined}
      />

      <p className="copy-hint">Select content in this page and copy for email, Notion, or an LP portal.</p>
    </main>
  );
}
