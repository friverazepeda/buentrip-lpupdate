# lpupdate GitHub issues backlog

A practical next-few-weeks issue list for `lpupdate`, organized by priority and written so each item can be copied into GitHub with minimal editing.

---

## Recommended labels

- `parser`
- `qa`
- `report-ui`
- `pipeline`
- `data-model`
- `infra`
- `high-priority`
- `good-first-followup`

---

## P0 — highest leverage

### 1) Fix AltScore asks extraction
**Labels:** `parser`, `qa`, `high-priority`

**Why**
AltScore metrics are good, but `asks_json` is still wrong because newsletter/repeated layout content bleeds into asks.

**Goal**
Make section parsing structure-aware enough to separate asks from highlights and repeated layout noise.

**Scope**
- inspect AltScore raw email structure
- improve section boundary detection
- prevent repeated/newsletter elements from being classified as asks
- validate output on current AltScore sample

**Acceptance criteria**
- `asks_json` contains only plausible asks/action requests
- highlights/achievements no longer leak into asks
- no obvious newsletter boilerplate appears in asks
- sample-based regression check added

**Notes**
Relevant area: `src/lpupdate/parse_updates.py`

---

### 2) Suppress Shippify appendix / audit contamination
**Labels:** `parser`, `qa`, `high-priority`

**Why**
Shippify metrics are useful, but appendix / audit-supporting text still leaks into `risks_json`.

**Goal**
Filter or downweight appendix-like content so only core update content feeds risks/highlights.

**Scope**
- identify appendix/audit signatures in the Shippify sample
- suppress or isolate non-core support text
- preserve real risks while excluding documentation noise

**Acceptance criteria**
- appendix/supporting text does not show up in `risks_json`
- highlights and risks are materially cleaner on Shippify
- regression check added for the sample

**Notes**
Look for audit appendix markers, support text, and repeated administrative language.

---

### 3) Improve Vertebra thread/reply parsing
**Labels:** `parser`, `qa`, `high-priority`

**Why**
Vertebra is safer than before, but still underparsed. The reply/thread format causes weak section extraction and the period remains null.

**Goal**
Handle thread-style forwarded/replied investor updates more intelligently.

**Scope**
- better cleanup for quoted thread markers and reply-chain formatting
- improve company and period inference from thread-style updates
- recover useful highlights/asks/risks where evidence exists

**Acceptance criteria**
- quoted reply junk is materially reduced
- period is inferred when supported by the source
- sections are extracted more intelligently instead of mostly suppressed
- regression check added for Vertebra sample

---

### 4) Add parser regression fixtures for current sample set
**Labels:** `qa`, `parser`, `high-priority`

**Why**
Parser quality is improving, but changes are risky without regression coverage.

**Goal**
Create a lightweight fixture-based regression suite covering current known samples.

**Scope**
- add fixtures/assertions for:
  - AltScore
  - Shippify
  - Vertebra
  - PayMon
  - Aloja
  - LEASY
  - MOX
  - Nuvocargo
- assert a small set of important expected outputs per sample
- document how to run the regression checks

**Acceptance criteria**
- parser changes can be validated against representative samples
- known-good metrics/period/company extraction are checked automatically
- known prior failure cases are encoded as tests or fixture assertions

---

## P1 — improve trust and usability

### 5) Add source excerpts for extracted metrics and sections
**Labels:** `parser`, `data-model`, `high-priority`

**Why**
It is still too hard to audit where parsed values came from.

**Goal**
Attach source snippets to parsed metrics and, if feasible, section items.

**Scope**
- add source excerpt fields to canonical parsed output
- start with metrics first
- extend to highlights/asks/risks if practical
- preserve backward compatibility as much as possible

**Acceptance criteria**
- each extracted metric includes a source snippet or excerpt
- sample inspection shows enough text to validate the extraction
- format is documented in project docs or code comments

---

### 6) Add confidence metadata for section-level extraction
**Labels:** `parser`, `qa`, `data-model`

**Why**
Metric confidence is improving, but section-level output still lacks a trust signal.

**Goal**
Store confidence metadata for highlights, asks, and risks.

**Scope**
- define confidence shape for section items
- populate confidence during parsing
- keep the signal simple and interpretable

**Acceptance criteria**
- parsed output includes confidence metadata for section items
- low-confidence section content can be identified downstream
- confidence semantics are documented

---

### 7) Implement incremental Gmail fetch / sync state
**Labels:** `pipeline`, `infra`, `high-priority`

**Why**
Current operation is still batch-oriented and reprocesses more than necessary.

**Goal**
Fetch and process only new labeled emails by default.

**Scope**
- store last-processed or last-seen state
- fetch only newer/missing Gmail messages
- preserve safe reruns and recovery behavior
- document how to force a full rescan when needed

**Acceptance criteria**
- default fetch path only processes new messages
- reruns are idempotent
- state is persisted clearly and safely
- there is a documented recovery/reset path

---

### 8) Make parse + sync idempotency explicit and tested
**Labels:** `pipeline`, `qa`

**Why**
Operational trust depends on safe repeated runs.

**Goal**
Ensure repeated fetch/parse/sync runs do not create accidental duplicates or inconsistent state.

**Scope**
- verify upsert behavior across the pipeline
- add checks/tests for rerunning same message batch
- document idempotent expectations

**Acceptance criteria**
- rerunning on the same message set is safe
- duplicate records are not created
- expected idempotent behavior is documented

---

### 9) Add reviewed / needs-review state for parsed updates
**Labels:** `qa`, `data-model`, `report-ui`

**Why**
There is no explicit distinction between machine output and trusted reviewed output.

**Goal**
Track whether a parsed report has been reviewed.

**Scope**
- define review status model
- store review status in DB and/or local metadata
- expose review status in inspection flow and report output

**Acceptance criteria**
- a report can be marked `reviewed` or `needs-review`
- status is queryable and visible in inspection/reporting flows
- default review state is sensible for newly parsed records

---

### 10) Build raw-vs-parsed review view
**Labels:** `qa`, `report-ui`, `pipeline`

**Why**
Reviewing parse quality is slow without a side-by-side comparison.

**Goal**
Create a simple review surface showing source content next to parsed fields.

**Scope**
- compare raw email / attachment text vs parsed output
- support key fields first: company, period, summary, metrics, asks, risks
- optimize for fast human QA, not beauty

**Acceptance criteria**
- reviewer can inspect source and parsed output together
- the view is usable for correcting extraction mistakes
- initial version supports at least one representative workflow

---

## P2 — report site / product layer

### 11) Add previous/next navigation between reports for a startup
**Labels:** `report-ui`, `good-first-followup`

**Why**
Startup pages now list report history, but detail pages still feel isolated.

**Goal**
Let users move between consecutive reports for the same startup.

**Scope**
- add older/newer navigation on report detail pages
- ensure ordering uses real timestamps, not string sort

**Acceptance criteria**
- each report page links to next newer / next older report where available
- navigation order is correct for multi-report startups like PayMon

---

### 12) Add startup-level comparison summary on history pages
**Labels:** `report-ui`

**Why**
Startup history pages are useful, but they are still mostly file lists.

**Goal**
Add a compact summary view above the report list.

**Scope**
- show report count
- latest period / latest received date
- optionally show latest key metrics or simple trend indicators

**Acceptance criteria**
- startup history page contains a useful summary block
- summary adds signal without cluttering the page

---

### 13) Highlight metric deltas between consecutive reports
**Labels:** `report-ui`, `parser`, `good-first-followup`

**Why**
The main analytical value is often what changed from one update to the next.

**Goal**
Show simple prior-vs-current changes for repeated metrics.

**Scope**
- match repeated metrics across consecutive reports
- display prior → current where confidence is reasonable
- avoid fake comparisons when matching is ambiguous

**Acceptance criteria**
- repeated comparable metrics show clear prior/current deltas
- ambiguous comparisons are skipped instead of hallucinated

---

### 14) Add parse-quality warnings to static report pages
**Labels:** `report-ui`, `qa`

**Why**
Users should see when a report is likely incomplete or low-confidence.

**Goal**
Expose visible parse-quality warnings on affected report pages.

**Examples**
- missing period
- sparse metrics
- low-confidence extraction
- attachment-heavy parse with weak body structure

**Acceptance criteria**
- affected reports show visible warnings
- warning rules are simple and understandable

---

### 15) Add portfolio-level search/filter to the static index
**Labels:** `report-ui`, `good-first-followup`

**Why**
The current index will become harder to use as more startups accumulate.

**Goal**
Add lightweight client-side filtering to the report index.

**Scope**
- filter by startup name
- optionally filter by investment vehicle
- keep it static-site friendly

**Acceptance criteria**
- filter works without a backend
- filtering is fast and intuitive

---

## P3 — BEM / hybrid evaluation

### 16) Wire real BEM endpoint into provider scaffold
**Labels:** `parser`, `infra`

**Why**
The provider abstraction exists, but BEM is still a scaffold.

**Goal**
Connect the real endpoint and save provider-native responses for evaluation.

**Scope**
- configure `BEM_API_URL`
- configure `BEM_API_KEY`
- validate request/response shape
- persist provider outputs under `data/provider_outputs/bem/`

**Acceptance criteria**
- BEM provider can run successfully against real samples
- provider-native outputs are stored for inspection
- failures are surfaced clearly

---

### 17) Define intermediate extraction schema for BEM output
**Labels:** `parser`, `data-model`

**Why**
Hybrid parsing works best if BEM produces a stable intermediate extraction shape instead of trying to write final DB-ready output directly.

**Goal**
Document and implement the intended intermediate schema.

**Suggested fields**
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

**Acceptance criteria**
- schema is documented
- provider output conforms to schema or is transformed into it
- hybrid merge logic has a stable contract

---

### 18) Evaluate rules vs hybrid on mixed startup sample set
**Labels:** `parser`, `qa`

**Why**
Need evidence before promoting hybrid parsing.

**Goal**
Run a side-by-side comparison on representative samples.

**Sample set**
- LEASY
- AltScore
- Shippify
- Vertebra
- MOX
- Nuvocargo
- PayMon

**Acceptance criteria**
- comparison writeup exists
- strengths/weaknesses by startup type are documented
- recommendation made on when hybrid should be used

---

## Suggested first sprint

If only a handful of issues are tackled immediately, start here:

1. Fix AltScore asks extraction
2. Suppress Shippify appendix contamination
3. Improve Vertebra thread parsing
4. Add parser regression fixtures
5. Add source excerpts for extracted metrics and sections
6. Implement incremental Gmail fetch / sync state
7. Add reviewed / needs-review state for parsed updates
8. Build raw-vs-parsed review view

---

## Notes

Current project status suggests the biggest leverage is still parser trustworthiness and reviewability, not new ingestion features. The reporting layer is now good enough to support review workflows, so the next step is making parsed output more auditable and easier to validate.
