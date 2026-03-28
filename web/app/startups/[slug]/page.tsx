import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { VehiclePills } from "@/components/vehicle-pills";
import { listStartupSlugs, loadStartupIndex } from "@/lib/reports-data";

type PageProps = { params: Promise<{ slug: string }> };

export function generateStaticParams() {
  return listStartupSlugs().map((slug) => ({ slug }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params;
  try {
    const s = loadStartupIndex(slug);
    return { title: `${s.name} — startup reports` };
  } catch {
    return { title: "Startup" };
  }
}

export default async function StartupPage({ params }: PageProps) {
  const { slug } = await params;
  let startup;
  try {
    startup = loadStartupIndex(slug);
  } catch {
    notFound();
  }

  const count = startup.report_count ?? startup.reports.length;

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
      {startup.reports.length === 0 ? (
        <p className="page-muted">No reports yet.</p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Period</th>
              <th>Received</th>
              <th>Subject</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {startup.reports.map((r) => (
              <tr key={r.report_id}>
                <td>{r.report_period_label ?? "—"}</td>
                <td>{r.received_at ?? "—"}</td>
                <td>{r.subject ?? "—"}</td>
                <td>
                  <Link href={`/startups/${startup.slug}/${r.report_id}/`}>Open</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <p className="copy-hint">Select content in this page and copy for email, Notion, or an LP portal.</p>
    </main>
  );
}
