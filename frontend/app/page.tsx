import type { Metadata } from "next";
import Link from "next/link";

import { VehiclePills } from "@/components/vehicle-pills";
import { loadPortfolioIndex } from "@/lib/reports-data";

export const metadata: Metadata = {
  title: "Portfolio overview — LP reports",
};

export default function PortfolioPage() {
  const data = loadPortfolioIndex();
  const title = data.title ?? "LP reports — portfolio overview";

  return (
    <main id="lp-report-export">
      <h1>{title}</h1>
      {data.intro ? <p className="page-muted">{data.intro}</p> : null}

      <section className="summary-grid" aria-label="Summary statistics">
        {data.summary_stats.map((s) => (
          <div key={s.label} className="summary-card">
            <div className="summary-card-label">{s.label}</div>
            <div className="summary-card-value">{s.value}</div>
          </div>
        ))}
      </section>

      {data.vehicle_groups.map((group) => (
        <section key={group.vehicle_title} className="vehicle-section">
          <h2>{group.vehicle_title}</h2>
          {group.rows.length === 0 ? (
            <p className="page-muted">No startups in this group.</p>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Startup</th>
                  <th>Vehicles</th>
                  <th>Latest period</th>
                  <th>Received</th>
                  <th>Subject</th>
                  <th>Report</th>
                </tr>
              </thead>
              <tbody>
                {group.rows.map((row) => (
                  <tr key={`${group.vehicle_title}-${row.slug}`}>
                    <td>
                      <Link href={`/startups/${row.slug}/`}>{row.name}</Link>
                    </td>
                    <td>
                      <VehiclePills vehicles={row.vehicles} />
                    </td>
                    <td>{row.latest_report.report_period_label ?? "—"}</td>
                    <td>{row.latest_report.received_at ?? "—"}</td>
                    <td>{row.latest_report.subject ?? "—"}</td>
                    <td>
                      <Link href={`/startups/${row.slug}/${row.latest_report.report_id}/`}>Open</Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      ))}

      <p className="copy-hint">Select content in this page and copy for email, Notion, or an LP portal.</p>
    </main>
  );
}
