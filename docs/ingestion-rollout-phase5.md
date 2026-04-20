# Phase 5 — Controlled rollout and verification

This phase is about **proving** that ingestion and persistence changes (observability, quarantine, parser resilience, `run_summary.json` files) behave correctly on a **fixed, repeatable** dataset before you rely on them against production mail and databases.

It complements unit tests by exercising the real CLI entrypoints and on-disk artifacts under `data/`.

## What you verify

1. **Parsed JSON contract** — every file in `data/parsed_updates/*.json` except `run_summary.json` has the fields and JSON types downstream code expects (see `lpupdate.rollout_verify.PARSED_REQUIRED_KEYS`).
2. **Sync summary integrity** — after `sync-postgres`, `data/parsed_updates/run_summary.json` describes `sync_postgres`, and:
   - `sum(skip_reasons.values()) == skipped`
   - `quarantined_count == skipped`
   - the `quarantine_dir` on disk contains exactly `quarantined_count` JSON files, each with a known `reason_code`
3. **No accidental ingestion of summaries** — `run_summary.json` is excluded from parse, sync, and static report generation (see `iter_data_record_json_files` in `src/lpupdate/store.py`).

## One-shot workflow (offline parse + sync)

From the **repository root**, with a virtualenv activated if you use one:

```bash
export PYTHONPATH=src
export LPUPDATE_PARSE_PROVIDER=rules
export LPUPDATE_DATABASE_URL='postgresql://USER:PASS@127.0.0.1:5432/TEST_DB'

python3 scripts/verify_ingestion_rollout.py bootstrap
python3 -m lpupdate.cli parse-raw --source all --limit 0
python3 -m lpupdate.cli db-apply
python3 -m lpupdate.cli sync-postgres --source all --limit 0
python3 scripts/verify_ingestion_rollout.py check --data-root .
```

If the last command prints `{"ok": true, ...}` and exit code `0`, the rollout checks passed for the current `data/` tree.

After **parse only** (no sync yet), use:

```bash
python3 scripts/verify_ingestion_rollout.py check --data-root . --parse-only
```

## Before / after comparisons on a real slice

When evaluating a code change against historical data:

1. Copy your existing `data/` directory to a backup path (or use a fresh git worktree).
2. Run the same bounded commands on both trees, for example `--limit 25` on fetch/parse/sync if you do not want “no limit”.
3. Compare:
   - `data/parsed_updates/run_summary.json` (stage, counters, `skip_reasons`, `quarantined_count`)
   - row counts in Postgres for `quarterly_updates` (or `lpupdate list-updates --limit 500`)
   - optional: `diff -ru` on `data/parsed_updates/` between backups (expect noise if parser output is non-deterministic across runs).

Treat **increases in `skipped` / quarantine** as a signal to inspect `reason_code` and raw email content, not necessarily a regression.

## Promoting changes safely

- Ship **one phase** of ingestion work at a time (observability → normalization → parser hardening → persistence audit).
- Re-run this Phase 5 checklist after each merge.
- Keep using unit tests for fast feedback: `cd src && python3 -m unittest discover -s lpupdate/tests -p 'test_*.py' -v`.

For **parser-level** regression fixtures (metric keys, period inference, company hints), see `docs/ingestion-parser-regression.md`.

---

## A.2 — Operational checks (CI + pinned parse-only runs)

**Goal:** Run Phase 5 **parse-only** verification automatically on every PR and offer a one-command local equivalent, without requiring Postgres or Gmail.

### What runs in CI

The workflow `.github/workflows/lpupdate-ci.yml`:

1. **`cd src && python3 -m unittest discover …`** — full `lpupdate` unit test suite (including parser regression A.1).
2. **`scripts/ci_phase5_parse_only.sh --clean`** — deletes `data/`, copies `rollout_samples` into `data/raw_*`, runs `parse-raw`, then `verify_ingestion_rollout.py check --parse-only`.

This proves the CLI, `run_summary.json` from `parse_raw`, and parsed JSON contract checks still work together.

### Local one-liner (same as CI)

Use Python **3.11+** and install dependencies once (same as CI: `pip install -e .` from the repo root). Then from the repository root:

```bash
./scripts/ci_phase5_parse_only.sh --clean
```

The script is executable in git; if your checkout strips the bit, run `chmod +x scripts/ci_phase5_parse_only.sh` once.

`--clean` removes `data/` first so the run matches CI and avoids stale raw/parsed files. Omit `--clean` only if you intentionally want to verify against whatever is already under `data/`.

### Full sync verification (not in default CI)

End-to-end checks including **quarantine** and **sync_postgres** `run_summary` still require `LPUPDATE_DATABASE_URL` and the commands in [One-shot workflow (offline parse + sync)](#one-shot-workflow-offline-parse--sync). Add a separate workflow with a Postgres service only when you want that path gated on every PR.
