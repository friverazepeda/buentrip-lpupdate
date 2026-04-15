import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { VehiclePills } from "@/components/vehicle-pills";

type PageProps = { params: Promise<{ slug: string }> };

type ApiStartup = {
  id: number;
  name: string;
  slug: string;
};

type StartupPageModel = {
  id: number;
  name: string;
  slug: string;
  vehicles: string[];
  report_count?: number;
};

type ApiStartupReport = {
  id: number;
  period_label?: string | null;
  quarter?: string | null;
  year?: number | null;
  received_at?: string | null;
};

async function loadStartupBySlug(slug: string): Promise<StartupPageModel | null> {
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
  const response = await fetch(`${apiBase}/api/startups/by-slug/${slug}/`, {
    cache: "no-store",
  });
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`);
  }
  const startup = (await response.json()) as ApiStartup;
  return {
    id: startup.id,
    name: startup.name,
    slug: startup.slug,
    // Backend endpoint currently returns id/name/slug only.
    vehicles: [],
  };
}

async function loadStartupReportsBySlug(slug: string): Promise<ApiStartupReport[]> {
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
  const response = await fetch(`${apiBase}/api/startups/by-slug/${slug}/reports/`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`);
  }
  const payload = (await response.json()) as unknown;
  return Array.isArray(payload) ? (payload as ApiStartupReport[]) : [];
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params;
  try {
    const s = await loadStartupBySlug(slug);
    if (!s) {
      return { title: "Startup" };
    }
    return { title: `${s.name} — startup reports` };
  } catch {
    return { title: "Startup" };
  }
}

export default async function StartupPage({ params }: PageProps) {
  const { slug } = await params;
  let startup: StartupPageModel | null;
  try {
    startup = await loadStartupBySlug(slug);
  } catch {
    notFound();
  }
  if (!startup) {
    notFound();
  }

  let reports: ApiStartupReport[] = [];
  try {
    reports = await loadStartupReportsBySlug(slug);
  } catch {
    reports = [];
  }

  const count = startup.report_count ?? reports.length;

  return (
    <main id="lp-report-export">
      <p>
        <Link href="/">← Portfolio overview</Link>
      </p>
      <h1>{startup.name}</h1>

      <div style={{ color: "#555", marginBottom: 24 }}>
        <div>
          <strong>Slug:</strong> {startup.slug}
        </div>
        <div style={{ marginTop: 8 }}>
          <strong>Reports on file:</strong> {count}
        </div>
        <div style={{ marginTop: 8 }}>
          <strong>Investment vehicles:</strong> <VehiclePills vehicles={startup.vehicles} />
        </div>
      </div>

      <h2>Reports</h2>
      {reports.length === 0 ? (
        <p className="page-muted">No reports yet.</p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Period</th>
              <th>Received</th>
              <th>Report ID</th>
            </tr>
          </thead>
          <tbody>
            {reports.map((r) => (
              <tr key={r.id}>
                <td>{r.period_label ?? `${r.quarter ?? "—"} ${r.year ?? ""}`.trim()}</td>
                <td>{r.received_at ?? "—"}</td>
                <td>{r.id}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <p className="copy-hint">Select content in this page and copy for email, Notion, or an LP portal.</p>
    </main>
  );
}
