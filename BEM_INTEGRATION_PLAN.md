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

## Why this shape

This keeps the system layered:
1. raw Gmail message + attachments
2. provider extraction result
3. canonical normalized parsed JSON
4. Postgres sync

That makes parser iteration safer and auditable.

## Immediate next step

Wire the real bem endpoint details into `src/lpupdate/parsers/bem.py`.

Right now the scaffold expects:
- `BEM_API_URL`
- `BEM_API_KEY`

And POSTs a JSON payload containing:
- message metadata
- body text
- attachment text
- a target extraction schema

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
  - `confidence`
  - `source_excerpt`

## Evaluation plan

Test first on a mixed batch:
- LEASY
- AltScore
- Shippify
- Vertebra
- MOX
- Nuvocargo

For each message compare:
- company detection
- period detection
- metric count
- critical metric coverage
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
