/** Normalized JSON contracts for LP report static rendering. */

export type IsoDateString = string;

export type PortfolioLatestReport = {
  report_id: string;
  report_period_label?: string | null;
  received_at?: string | null;
  subject?: string | null;
};

export type PortfolioRow = {
  slug: string;
  name: string;
  vehicles: string[];
  latest_report: PortfolioLatestReport;
};

export type PortfolioVehicleGroup = {
  vehicle_title: string;
  rows: PortfolioRow[];
};

export type SummaryStat = {
  label: string;
  value: number | string;
};

export type PortfolioIndex = {
  title?: string;
  intro?: string | null;
  summary_stats: SummaryStat[];
  vehicle_groups: PortfolioVehicleGroup[];
};

export type StartupReportRef = {
  report_id: string;
  report_period_label?: string | null;
  received_at?: string | null;
  subject?: string | null;
};

export type StartupIndex = {
  slug: string;
  name: string;
  vehicles: string[];
  /** Total reports if known; otherwise UI derives from `reports.length`. */
  report_count?: number;
  reports: StartupReportRef[];
};

export type ReportMeta = {
  report_period_label?: string | null;
  received_at?: string | null;
  subject?: string | null;
  gmail_message_id?: string | null;
  [key: string]: unknown;
};

export type ReportDetail = {
  report_id: string;
  startup: { slug: string; name: string };
  vehicles: string[];
  meta: ReportMeta;
  summary?: string | null;
  metrics?: Record<string, unknown> | null;
  highlights?: string[] | null;
  asks?: string[] | null;
  risks?: string[] | null;
};
