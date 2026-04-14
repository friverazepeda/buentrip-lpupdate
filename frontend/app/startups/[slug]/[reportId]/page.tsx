import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { ReportSections } from "@/components/report-body";
import { VehiclePills } from "@/components/vehicle-pills";
import type { ReportMeta } from "@/lib/types";
import { generateAllReportParams, loadReportDetail } from "@/lib/reports-data";

type PageProps = { params: Promise<{ slug: string; reportId: string }> };

const META_FIRST = ["report_period_label", "received_at", "subject", "gmail_message_id"] as const;

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

export function generateStaticParams() {
  return generateAllReportParams();
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug, reportId } = await params;
  try {
    const r = loadReportDetail(slug, reportId);
    const period = r.meta.report_period_label ?? reportId;
    return { title: `${r.startup.name} — ${period}` };
  } catch {
    return { title: "Report" };
  }
}

export default async function ReportPage({ params }: PageProps) {
  const { slug, reportId } = await params;
  let report;
  try {
    report = loadReportDetail(slug, reportId);
  } catch {
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
