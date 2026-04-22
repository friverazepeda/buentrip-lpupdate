import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { ReportEditor } from "./report-editor";

type PageProps = { params: Promise<{ id: string }> };

type ReportDetail = {
  id: number;
  vehicle_name?: string | null;
  report_period_label?: string | null;
  status?: string | null;
  summary_of_progress?: string | null;
  significant_developments?: string | null;
  startup_updates?: Array<{
    id: number;
    startup_name?: string | null;
    period_label?: string | null;
    summary?: string | null;
    highlights?: string[] | null;
    risks?: string[] | null;
    asks?: string[] | null;
  }> | null;
};

async function loadReport(id: string): Promise<ReportDetail | null> {
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
  const response = await fetch(`${apiBase}/api/lp-reports/?id=${id}`, { cache: "no-store" });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`Request failed with status ${response.status}`);
  return (await response.json()) as ReportDetail;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { id } = await params;
  try {
    const report = await loadReport(id);
    if (!report) return { title: "LP Report" };
    return { title: `${report.vehicle_name || "Vehicle"} — ${report.report_period_label || "LP Report"}` };
  } catch {
    return { title: "LP Report" };
  }
}

export default async function LpReportDetailPage({ params }: PageProps) {
  const { id } = await params;
  const report = await loadReport(id);
  if (!report) notFound();
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
  return (
    <main>
      <p>
        <Link href="/">← Portfolio</Link>
        {" · "}
        <Link href="/lp-reports">← LP Reports</Link>
      </p>
      <h1>Quarterly LP Report</h1>
      <ReportEditor initialReport={report} apiBase={apiBase} />
    </main>
  );
}
