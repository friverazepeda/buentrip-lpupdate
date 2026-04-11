# bem integration plan for lpupdate

## What changed

A provider-based parsing layer now sits between raw Gmail source assembly and parsed JSON output.

Current providers:
- `rules` — existing parser in `src/lpupdate/parse_updates.py`
- `bem` — remote structured extraction scaffold in `src/lpupdate/parsers/bem.py`
- `hybrid` — merges bem output with rules fallback in `src/lpupdate/parsers/hybrid.py`

The CLI entrypoint `parse-raw` now:
1. loads raw Gmail JSON
2. assembles attachment text into a source bundle
3. dispatches to the selected provider
4. writes canonical parsed JSON to `data/parsed_updates/`
5. writes provider-native output to `data/provider_outputs/<provider>/`

## Current wiring status (2026-03-27)

- `BemParseProvider` now calls the v2 `/calls` endpoint, injects the structured schema from `bem_schema.json`, and handles the multi-metric payloads that v2 emits.
- Workflow slug + response behavior are configurable via `BEM_WORKFLOW_NAME` / `BEM_FUNCTION_NAME`; payload text is base64-encoded per BEM's `singleFile.inputContent` contract, and we poll `/v2/calls/{callID}` so `transformedContent` is available synchronously for downstream normalization.
- Section lists (highlights / asks / challenges) and contact records are normalized so the downstream pipeline still receives arrays.
- Confidence + metric dictionaries are keyed by slugged metric names to keep the hybrid merge path deterministic.
- Secrets stay outside git: `bem_config.json` remains local-only and `.gitignore` now blocks it by default.
- Added `samples/bem_eval_samples.json` with the curated Gmail IDs (Leasy, AltScore, Shippify, Vertebra, MOX, Nuvocargo, PayMon, Aloja) plus the `lpupdate bem-sample-run` CLI helper that runs any provider on that list and dumps parsed/provider JSON under `data/provider_samples/<provider>/`.

## Why this shape

This keeps the system layered:
1. raw Gmail message + attachments
2. provider extraction result
3. canonical normalized parsed JSON
4. Postgres sync

That makes parser iteration safer and auditable.

## Immediate next step

Run `lpupdate bem-sample-run --provider bem` (and again with `--provider hybrid`) to collect v2 baselines for the curated sample set. Use those outputs to compare against the existing `rules` results.

While doing that, focus on:
- verifying schema coverage (company/period/sections) across each sample
- ensuring metrics arrays return more than one record when present in the deck/email
- capturing any hallucinations or missing sections in the provider output JSON

## Recommended first bem workflow

Ask bem for an intermediate extraction schema, not final DB shape.

Suggested output:
- `company_name_raw`
- `reporting_period_raw`
- `summary`
- `highlights[]`
- `asks[]`
- `risks[]`
- `metrics[]` with:
  - `name_raw`
  - `canonical_name`
  - `value_raw`
  - `value_type`
  - `numeric_value`
  - `unit`
  - `period`
  - `source_excerpt`

(This schema lives in `bem_schema.json` and can be overridden via `BEM_SCHEMA_PATH`.)

## Evaluation plan

Test first on a mixed batch:
- LEASY
- AltScore
- Shippify
- Vertebra
- MOX
- Nuvocargo
- PayMon
- Aloja

Command:
```bash
LPUPDATE_PARSE_PROVIDER=bem lpupdate bem-sample-run
LPUPDATE_PARSE_PROVIDER=hybrid lpupdate bem-sample-run --provider hybrid
```

For each message compare:
- company detection
- period detection
- metric count / coverage
- bad/hallucinated metrics
- section quality for highlights / asks / risks

## Rollout plan

### Phase 1
Use `LPUPDATE_PARSE_PROVIDER=hybrid` on a small sample batch.

### Phase 2
Tune bem schema/workflow until it beats rules for:
- PDF decks
- table-heavy updates
- thread-style messy updates

### Phase 3
Move production parsing to `hybrid`, keep rules as deterministic fallback.

## Notes

`sync-postgres` does not need major changes yet because parsed JSON remains backward-compatible enough for the current DB sync path.
