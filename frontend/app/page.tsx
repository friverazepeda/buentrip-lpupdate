"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

type ApiStartup = {
  id: number;
  name: string;
  slug: string;
};

export default function PortfolioPage() {
  const [startups, setStartups] = useState<ApiStartup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
    const controller = new AbortController();

    async function loadStartups() {
      setLoading(true);
      setError(null);
      try {
        const requestUrl = `${apiBase}/api/startups/`;
        console.log("Fetching startups from:", requestUrl);
      
        const response = await fetch(requestUrl, {
          signal: controller.signal,
          cache: "no-store",
        });
      
        if (!response.ok) {
          throw new Error(`Request failed with status ${response.status}`);
        }
      
        const payload = (await response.json()) as unknown;
        console.log("API response payload:", payload);
      
        const list = Array.isArray(payload) ? payload : [];
        setStartups(list as ApiStartup[]);
      
        
      } catch (err) {
        const aborted =
          err instanceof DOMException
            ? err.name === "AbortError"
            : err instanceof Error && err.name === "AbortError";
        if (aborted) {
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load startups");
      } finally {
        setLoading(false);
      }
    }

    void loadStartups();

    return () => {
      controller.abort();
    };
  }, []);

  return (
    <main id="lp-report-export">
      <h1>LP reports — portfolio overview</h1>
      <p className="page-muted">Startup list loaded from the Django API endpoint at <code>/api/startups/</code>.</p>
      <section className="summary-grid" aria-label="Summary statistics">
        <div className="summary-card">
          <div className="summary-card-label">Total startups</div>
          <div className="summary-card-value">{loading ? "…" : startups.length}</div>
        </div>
      </section>

      <section className="vehicle-section">
        <h2>Startups</h2>
        {loading ? <p className="page-muted">Loading startups...</p> : null}
        {!loading && error ? <p className="page-muted">Could not load startups: {error}</p> : null}
        {!loading && !error && startups.length === 0 ? <p className="page-muted">No startups found.</p> : null}
        {!loading && !error && startups.length > 0 ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Startup</th>
                <th>Slug</th>
                <th>Startup page</th>
              </tr>
            </thead>
            <tbody>
              {startups.map((startup) => (
                <tr key={startup.id}>
                  <td>{startup.name}</td>
                  <td>{startup.slug}</td>
                  <td>
                    <Link href={`/startups/${startup.slug}/`}>Open</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </section>

      <p className="copy-hint">Select content in this page and copy for email, Notion, or an LP portal.</p>
    </main>
  );
}
