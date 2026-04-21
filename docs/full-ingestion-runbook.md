# Full ingestion runbook (Gmail + Fathom → Postgres)

Use this when you want a **fresh pull** from Gmail and Fathom, **re-parse** everything under `data/raw_*`, and **reload** the **lpupdate** Postgres tables so structured data matches the latest parser.

This document applies to **`LPUPDATE_DATABASE_URL`** (the pipeline / `src/lpupdate` schema: `companies`, `email_messages`, `quarterly_updates`, `attachments`). It is **not** the Django app database unless you intentionally point both at the same URL.

## Prerequisites

- Python **3.11+**, repo root, dependencies: `pip install -e .`
- **`PYTHONPATH=src`** (or `pip install -e .` so `lpupdate` is importable)
- **`.env`** (or environment) with at least:
  - `LPUPDATE_DATABASE_URL` — Postgres URL for the pipeline schema
  - `FATHOM_API_KEY` — for Fathom fetch
  - Gmail: `GOOGLE_OAUTH_*`, `GMAIL_QUERY`, etc. (see `lpupdate doctor`)
- **Parse provider:** `LPUPDATE_PARSE_PROVIDER` or pass `--provider` on `run-pipeline` (now honored for the parse step).

## One-shot: fetch → parse → sync → reports

From the **repository root**:

```bash
export PYTHONPATH=src
# optional: which parser backend for parse-raw (run-pipeline sets this for the run)
export LPUPDATE_PARSE_PROVIDER=hybrid   # or rules, bem

lpupdate db-apply
lpupdate db-reset --yes    # optional: empty lpupdate tables before sync (see below)
lpupdate run-pipeline --limit 0 --provider hybrid --source all
```

- **`--limit 0`** means no cap on **parse**, **sync**, and **Fathom** fetch. For **Gmail**, `0` means “fetch every message matching `GMAIL_QUERY`” by **paginating** `messages.list` (500 IDs per request). Omitting `maxResults` or using `0` incorrectly used to hit Gmail’s **default of 100** per call or **`maxResults=0` (HTTP 400)**; the CLI now paginates until `nextPageToken` is absent.
- **`db-reset --yes`** **deletes all rows** in `attachments`, `quarterly_updates`, `email_messages`, and `companies` on **`LPUPDATE_DATABASE_URL`**. Use when you want the DB to reflect **only** what you just fetched and parsed, without leftover rows from older message IDs. **Back up first** if unsure.

After a reset, the next **`sync-postgres`** repopulates companies and updates from `data/parsed_updates/` and raw files.

## Optional: clean local `data/` first

If you want **only** what this run pulls (no stale `data/raw_*` or `data/parsed_updates`):

```bash
rm -rf data
```

Then run the pipeline (it will recreate `data/` on fetch). **Warning:** this deletes local raw archives; keep backups if you need history offline.

## Verify

```bash
lpupdate list-updates --limit 50
lpupdate list-companies
```

Inspect summaries:

```bash
cat data/parsed_updates/run_summary.json
```

## Django / Next.js vs lpupdate Postgres

- **Pipeline DB** (`lpupdate` CLI, `LPUPDATE_DATABASE_URL`): source for `list-updates`, `show-update`, and the ingestion work in `src/lpupdate/db.py`.
- **Django + Next report UI** often use a **separate** DB with models like `StartupUpdate`. Refreshing those is a **second step** (e.g. `scripts/migrate_data.py` or your own sync) after you are happy with lpupdate data.

See `docs/ingestion-parser-regression.md` and `docs/stage-b-parser-quality.md` for improving **decision-useful** parsed output (Stage B).
