import fs from "fs";
import path from "path";

import type { PortfolioIndex, ReportDetail, StartupIndex } from "./types";

/** Source JSON: `public/reports/...` (served as `/reports/...` after export). */
export const REPORTS_DIR = path.join(process.cwd(), "public", "reports");

function readJson<T>(file: string): T {
  return JSON.parse(fs.readFileSync(file, "utf8")) as T;
}

export function loadPortfolioIndex(): PortfolioIndex {
  return readJson<PortfolioIndex>(path.join(REPORTS_DIR, "index.json"));
}

const SAFE_SEGMENT = /^[-a-zA-Z0-9_.]+$/;

function assertSafeSegment(name: string, label: string): void {
  if (!SAFE_SEGMENT.test(name)) {
    throw new Error(`Invalid ${label}`);
  }
}

export function loadStartupIndex(slug: string): StartupIndex {
  assertSafeSegment(slug, "slug");
  return readJson<StartupIndex>(path.join(REPORTS_DIR, "startups", slug, "index.json"));
}

export function loadReportDetail(slug: string, reportId: string): ReportDetail {
  assertSafeSegment(slug, "slug");
  assertSafeSegment(reportId, "report id");
  return readJson<ReportDetail>(path.join(REPORTS_DIR, "startups", slug, `${reportId}.json`));
}

export function listStartupSlugs(): string[] {
  const dir = path.join(REPORTS_DIR, "startups");
  if (!fs.existsSync(dir)) return [];
  return fs
    .readdirSync(dir, { withFileTypes: true })
    .filter((d) => d.isDirectory())
    .map((d) => d.name);
}

export function listReportIdsForSlug(slug: string): string[] {
  const dir = path.join(REPORTS_DIR, "startups", slug);
  if (!fs.existsSync(dir)) return [];
  return fs
    .readdirSync(dir)
    .filter((f) => f.endsWith(".json") && f !== "index.json")
    .map((f) => path.basename(f, ".json"));
}

export function generateAllReportParams(): { slug: string; reportId: string }[] {
  const pairs: { slug: string; reportId: string }[] = [];
  for (const slug of listStartupSlugs()) {
    for (const reportId of listReportIdsForSlug(slug)) {
      pairs.push({ slug, reportId });
    }
  }
  return pairs;
}
