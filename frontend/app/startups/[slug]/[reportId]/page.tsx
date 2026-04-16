import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { VehiclePills } from "@/components/vehicle-pills";

type PageProps = { params: Promise<{ slug: string; reportId: string }> };

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
  subject?: string | null;
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

type NormalizedMetric = {
  label: string;
  value: string;
  unit?: string;
  note?: string;
};

type NormalizedReportDetail = {
  startupName: string;
  reportPeriod: string;
  receivedAt: string;
  subject: string;
  investmentVehicles: string[];
  summary: string;
  metrics: NormalizedMetric[];
  highlights: string[];
  asks: string[];
  risks: string[];
};

function toLines(value?: string | null): string[] {
  if (!value) return [];
  return value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function normalizeReportDetail(rawReport: ApiReport): NormalizedReportDetail {
  const startupName = rawReport.startup_name?.trim() || "Startup";
  const reportPeriod = rawReport.period_label?.trim() || `${rawReport.quarter ?? ""} ${rawReport.year ?? ""}`.trim() || "";
  const receivedAt = rawReport.received_at?.trim() || "";
  const subject = rawReport.subject?.trim() || "";
  const investmentVehicles = rawReport.vehicle_name?.trim() ? [rawReport.vehicle_name.trim()] : [];

  const summary = [rawReport.opportunities_and_challenges, rawReport.fundraising_updates]
    .map((part) => (part ?? "").trim())
    .filter(Boolean)
    .join("\n\n");

  const metrics: NormalizedMetric[] = (rawReport.metrics ?? []).map((metric, index) => ({
    label: metric.name?.trim() || `Metric ${index + 1}`,
    value: metric.value?.trim() || "",
    note: metric.change?.trim() || undefined,
  }));

  return {
    startupName,
    reportPeriod,
    receivedAt,
    subject,
    investmentVehicles,
    summary,
    metrics,
    highlights: toLines(rawReport.highlights),
    asks: toLines(rawReport.asks),
    risks: toLines(rawReport.risks),
  };
}

async function loadReportById(reportId: string): Promise<NormalizedReportDetail | null> {
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
  const response = await fetch(`${apiBase}/api/reports/${reportId}/`, { cache: "no-store" });
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`);
  }

  const raw = (await response.json()) as ApiReport;
  return normalizeReportDetail(raw);
}

function BulletSection({ title, items }: { title: string; items?: string[] | null }) {
  const cleaned = (items ?? []).filter((item) => item && item.trim());
  return (
    <section style={{ border: "1px solid #ddd", borderRadius: 8, padding: 16, margin: "18px 0" }}>
      <h2 style={{ color: "#16324f", marginBottom: 12 }}>{title}</h2>
      {cleaned.length === 0 ? (
        <p style={{ color: "#555" }}>None</p>
      ) : (
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          {cleaned.map((item) => (
            <li key={item} style={{ marginBottom: 8 }}>
              {item}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function MetricsSection({ metrics }: { metrics: NormalizedMetric[] }) {
  const visibleMetrics = metrics.filter(
    (metric) =>
      Boolean(metric.label?.trim()) || Boolean(metric.value?.trim()) || Boolean(metric.unit?.trim()) || Boolean(metric.note?.trim()),
  );
  return (
    <section style={{ border: "1px solid #ddd", borderRadius: 8, padding: 16, margin: "18px 0" }}>
      <h2 style={{ color: "#16324f", marginBottom: 12 }}>Key Metrics</h2>
      {visibleMetrics.length === 0 ? (
        <p style={{ color: "#555", margin: 0 }}>No key metrics parsed.</p>
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: 12,
          }}
        >
          {visibleMetrics.map((metric) => (
            <article
              key={`${metric.label}-${metric.value}-${metric.note ?? ""}`}
              style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: 12, background: "#f9fafb" }}
            >
              <div style={{ fontSize: 13, color: "#526172", marginBottom: 6 }}>{metric.label}</div>
              <div style={{ fontSize: 20, fontWeight: 600, color: "#16324f", lineHeight: 1.3 }}>
                {metric.value}
                {metric.unit ? ` ${metric.unit}` : ""}
              </div>
              {metric.note ? <div style={{ marginTop: 6, color: "#374151", fontSize: 13 }}>{metric.note}</div> : null}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { reportId } = await params;
  try {
    const r = await loadReportById(reportId);
    if (!r) {
      return { title: "Report" };
    }
    const period = r.reportPeriod || reportId;
    return { title: `${r.startupName} — ${period}` };
  } catch {
    return { title: "Report" };
  }
}

export default async function ReportPage({ params }: PageProps) {
  const { slug, reportId } = await params;
  let report: NormalizedReportDetail | null;
  try {
    report = await loadReportById(reportId);
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
        <Link href={`/startups/${slug}/`}>← {report.startupName}</Link>
      </p>

      <h1>{report.startupName}</h1>

      <div style={{ color: "#555", marginBottom: 16 }}>
        <div style={{ marginBottom: 8 }}>
          <strong>Report period:</strong> {report.reportPeriod || "—"}
        </div>
        <div style={{ marginBottom: 8 }}>
          <strong>Received at:</strong> {report.receivedAt || "—"}
        </div>
        <div style={{ marginBottom: 8 }}>
          <strong>Subject:</strong> {report.subject || "—"}
        </div>
        <div>
          <strong>Investment vehicles:</strong> <VehiclePills vehicles={report.investmentVehicles} />
        </div>
      </div>

      <section style={{ border: "1px solid #ddd", borderRadius: 8, padding: 16, margin: "18px 0" }}>
        <h2 style={{ color: "#16324f", marginBottom: 12 }}>Summary</h2>
        {report.summary.trim() ? (
          <p style={{ whiteSpace: "pre-wrap", margin: 0 }}>{report.summary}</p>
        ) : (
          <p style={{ color: "#555", margin: 0 }}>None</p>
        )}
      </section>

      <MetricsSection metrics={report.metrics} />

      <BulletSection title="Highlights" items={report.highlights} />
      <BulletSection title="Asks" items={report.asks} />
      <BulletSection title="Risks" items={report.risks} />

      <p className="copy-hint">Select content in this page and copy for email, Notion, or an LP portal.</p>
    </main>
  );
}
