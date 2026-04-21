# Stage B — Parser quality: structured data that is decision-useful

**Stage A** (observability, regression fixtures, Phase 5 CI) makes changes **safe**. **Stage B** raises **quality**: metrics, sections, and confidence that match how you read real updates—not only that fields exist.

This doc ties together priorities from `PROJECT_PLAN.md` (“Recommended next development priorities”) and `GITHUB_ISSUES_BACKLOG.md` (P0 parser items).

## Goals

1. **Reduce false structure** — wrong sections (e.g. newsletter text in `asks_json`), appendix text in `risks_json`, weak thread/reply handling.
2. **Improve metric signal** — fewer spurious KPIs; clearer money and ranges; optional snippets/confidence already partially modeled in `confidence_json`.
3. **Lock gains with fixtures** — each fix adds or extends a case under `src/lpupdate/tests/fixtures/parser_regression/` (see `docs/ingestion-parser-regression.md`).

## Suggested order of work

| Priority | Focus | Primary module | Notes |
|----------|--------|----------------|--------|
| B1 | AltScore-style asks vs layout noise | `parse_updates.py` section boundaries | Backlog P0 #1 |
| B2 | Shippify appendix / audit leakage into risks | `parse_updates.py` filtering / hints | Backlog P0 #2 |
| B3 | Vertebra-style threads / period inference | `parse_updates.py`, possibly ingest cleanup | Backlog P0 #3 |
| B4 | PDF / deck KPI lines | `parse_updates.py`, `pdf_extract.py`, optional BEM | PROJECT_PLAN Priority 2 |
| B5 | Metric confidence + display | `parse_updates.py`, `metrics_display.py`, API consumers | PROJECT_PLAN Priority 1 “Planned additions” |

## After a full ingestion run

Once `run-pipeline` + optional `db-reset` has landed fresh data (`docs/full-ingestion-runbook.md`):

1. Spot-check **`metrics_json`** and narrative fields via `lpupdate show-update <id>` or SQL.
2. For portfolio-specific issues, add a **small regression fixture** before changing heuristics.
3. Re-run **`cd src && python3 -m unittest discover -s lpupdate/tests -p 'test_*.py'`** and CI Phase 5 script as appropriate.

## Exit criteria (rolling)

- Parser regression tests pass; new cases added for each fixed company pattern.
- Quarantine / skip counts explained by `reason_code`, not silent bad structure.
- Web/API consumers receive **readable** metric strings where Django migration applies (`format_metric_value_for_display` in `scripts/migrate_data.py`).
