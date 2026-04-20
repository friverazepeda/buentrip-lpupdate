# Parser regression suite (roadmap A.1)

This document describes the **fixture-based parser regression** workflow, how it relates to **Phase 5 rollout** checks, and how to **verify metrics** from parsed JSON through the Django API to the Next.js report UI.

## Goals

1. **Catch regressions** when editing `src/lpupdate/parse_updates.py` (and related rules-layer code) without relying on live Gmail or BEM.
2. **Encode expectations** for a growing set of company- or pattern-specific cases (AltScore-style layout, Shippify appendix noise, etc.) using **small JSON fixtures** rather than full mailbox exports.
3. **Align metrics display** with what operators and LPs expect to see in the web app—not Python `repr()` of dicts.

## What the regression tests do

- **Module:** `src/lpupdate/tests/test_parser_regression.py`
- **Fixtures:** `src/lpupdate/tests/fixtures/parser_regression/*.json`

Each fixture file has:

- `id` — short name for logs
- `raw` — a minimal Gmail-shaped dict passed to `normalize_update()` (same shape as raw archive JSON: `gmail_message_id`, `subject`, `body_text`, `received_at`, optional `company_name_hint`, …)
- `expected` — assertions:
  - `metrics_keys_contain` — every listed key must appear in `metrics_json` after parsing
  - `min_metric_count` — minimum number of metric keys
  - `report_year` — optional exact match
  - `company_name_contains` — substring that must appear in resolved `company_name` (often used with `company_name_hint` in `raw`)

The tests use the **rules** parser output path via `normalize_update()` only (no BEM / hybrid API calls), so they run quickly in CI and offline environments.

### Run the tests

From the repository root:

```bash
cd src
python3 -m unittest lpupdate.tests.test_parser_regression -v
```

Run together with other `lpupdate` tests:

```bash
cd src
python3 -m unittest discover -s lpupdate/tests -p 'test_*.py' -v
```

### Add a new fixture

1. Copy an existing JSON file under `src/lpupdate/tests/fixtures/parser_regression/`.
2. Prefer **synthetic or anonymized** body text that still triggers the behavior you care about (section boundaries, KPI lines, etc.). Do not commit confidential email content.
3. Tune `expected` to be **stable**: assert on metric **keys** and coarse fields (`report_year`, `company_name_contains`) rather than full JSON equality of `metrics_json` values (values can be floats/dicts and may shift slightly with heuristics).
4. For real portfolio names (AltScore, Shippify, …), add a dedicated fixture when you have a safe excerpt; link the fixture `id` to the issue in `GITHUB_ISSUES_BACKLOG.md` if useful.

## Metrics: from parser to web UI

Parsed metrics live in **`metrics_json`** on the lpupdate/Postgres `quarterly_updates` side (`src/lpupdate/schema.py`). Values are often **structured** (e.g. `{"value": 2600000, "currency": "USD", "period": "annual"}`), not plain strings.

### Django app (`dashboard`)

The legacy migration script `scripts/migrate_data.py` copies lpupdate rows into Django `StartupUpdate` + `StartupMetric`. Each `StartupMetric` has **string** fields `name`, `value`, `change`.

Previously, `value` was set with `str(v)` on Python objects, which produced **single-quoted dict reprs** and looked like “raw JSON” or garbage in the API and frontend.

**Now:** use `format_metric_value_for_display()` from `src/lpupdate/metrics_display.py` when creating `StartupMetric` rows so money and structured values become **short, readable strings** (e.g. `$2.60M (annual)`).

**Note:** Existing rows in the DB are unchanged until you re-migrate or edit them. New runs of `migrate_data.py` for **newly created** reports get the improved formatting on the `if created:` path.

### JSON API (`GET /api/reports/<id>/`)

`dashboard/views.py` exposes:

```text
metrics: [ { "name": "...", "value": "...", "change": "..." }, ... ]
```

The Next.js report page (`frontend/app/startups/[slug]/[reportId]/page.tsx`) maps `name` → label and `value` → displayed value. If `metrics` is empty, the UI correctly shows the empty state / “no metrics” messaging.

### End-to-end checks when metrics look wrong

1. **Parser layer:** Run parser regression tests; add a fixture if the bug is reproducible with a small `raw` payload.
2. **lpupdate DB:** Inspect `metrics_json` for the corresponding `quarterly_updates` row (CLI `show-update` or SQL). Confirm keys and shapes.
3. **Django:** Confirm `StartupMetric` rows exist for that `StartupUpdate` and that `value` is readable text, not a Python repr.
4. **API:** `curl` or browser `GET /api/reports/<id>/` and inspect the `metrics` array.
5. **Frontend:** Hard-refresh; confirm `NEXT_PUBLIC_API_BASE_URL` points at the Django server you inspected.

If `metrics_json` is populated but Django shows no metrics, the data path may not have run `migrate_data.py` for that row, or the report was updated without re-creating metrics (see script logic). Fixing that is a data/ops concern separate from parser tuning.

## Relation to Phase 5 rollout verification

- **Phase 5** (`docs/ingestion-rollout-phase5.md`) validates **pipeline artifacts** (`run_summary.json`, quarantine, parsed file shapes) on a full `parse-raw` → `sync-postgres` run.
- **Parser regression** (this doc) validates **rules-layer parsing behavior** on isolated fixtures.

Run both after meaningful ingestion or parser changes.
