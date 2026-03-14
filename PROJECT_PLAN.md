# lpupdate — Initial Project Development Plan

## Objective

Build a system that:
- reads Google Workspace email from Gmail
- targets messages labeled `Investor/Quarterly`
- preserves raw source material
- parses highly variable startup investor updates
- stores structured and semi-structured outputs in a way that supports:
  - flexible metrics across companies
  - changing metrics over time
  - narrative analysis
  - historical comparison

---

## Why this architecture

Startup updates are inconsistent.

Common problems:
- not every company reports the same KPIs
- the same company changes what it reports over time
- some updates are mostly narrative
- others are KPI decks or PDF attachments
- naming is inconsistent (`ARR`, `Annualized Revenue`, `Revenue run-rate`, etc.)
- the most important signal is sometimes qualitative rather than numeric

Because of that, a rigid schema alone is a bad fit.

### Chosen approach
- **Raw source preservation** for auditability
- **Flexible normalized records** for querying and comparison
- **Postgres + JSONB** as the main store
- **Attachments/PDF extraction** included in the ingestion path

This gives us:
- production-friendly storage
- flexible metrics
- ability to query across companies
- ability to preserve source-of-truth materials

---

## Development phases

## Phase 1 — Gmail ingestion

### Goal
Authenticate to Gmail and fetch messages with label `Investor/Quarterly`.

### Deliverables
- Gmail OAuth flow
- Gmail label lookup
- raw message fetch
- local storage of raw source JSON

### Status
Completed.

### Notes
Current Gmail account used for development:
- `manuel@buentrip.vc`

Current label:
- `Investor/Quarterly`

---

## Phase 2 — Raw source archive

### Goal
Preserve source material before trying to parse it.

### Deliverables
- save raw message JSON locally
- preserve body text
- preserve body HTML
- preserve Gmail metadata
- preserve attachment metadata

### Storage
- `projects/lpupdate/data/raw_gmail/`

### Status
Completed.

---

## Phase 3 — Attachment and PDF ingestion

### Goal
Download attachments and extract text from PDFs so deck-style investor updates are parseable.

### Deliverables
- attachment discovery in Gmail payloads
- attachment download
- local attachment storage
- PDF text extraction
- merge attachment text into parsing pipeline

### Storage
- `projects/lpupdate/data/attachments/<gmail_message_id>/`

### Status
Completed for local development.

### Notes
This is especially important for companies like LEASY, where KPI decks are attached as PDFs.

---

## Phase 4 — First-pass parser

### Goal
Convert raw email + attachment text into normalized update records.

### Deliverables
- infer company name
- infer reporting period
- extract summary
- extract highlights
- extract asks
- extract risks when possible
- extract flexible metrics into JSON

### Storage
- `projects/lpupdate/data/parsed_updates/`

### Status
Completed as a first-pass parser.

### Current extracted fields
- `company_name`
- `report_period_label`
- `report_quarter`
- `report_year`
- `report_month`
- `summary`
- `metrics_json`
- `highlights_json`
- `asks_json`
- `risks_json`
- `people_json`

---

## Phase 5 — Flexible local database

### Goal
Persist parsed outputs into a development database with a production-compatible shape.

### Chosen database
- local Postgres on Ubuntu server

### Why local Postgres first
- proper JSONB support
- close to production behavior
- avoids designing around SQLite limitations
- easier future migration to remote Postgres

### Tables
- `companies`
- `email_messages`
- `quarterly_updates`
- `attachments`

### Status
Completed for local development.

### Local development connection
- database: `lpupdate`
- user: `lpupdate`
- URL: `postgresql://lpupdate:lpupdate_dev_password@localhost:5432/lpupdate`

---

## Phase 6 — Inspection and developer tooling

### Goal
Make it easy to inspect data without raw SQL.

### Deliverables
CLI commands for:
- health/config checks
- fetch
- parse
- sync to Postgres
- inspect updates
- inspect companies
- inspect metrics
- inspect raw emails
- inspect attachment text

### Current CLI commands
- `doctor`
- `gmail-auth`
- `gmail-check`
- `gmail-fetch`
- `parse-raw`
- `db-apply`
- `sync-postgres`
- `list-updates`
- `show-update`
- `list-companies`
- `show-company`
- `company-metrics`
- `show-raw-email`
- `show-attachment-text`

### Status
Completed for local development.

---

## Current system status

The current local development pipeline works end-to-end:

1. Gmail auth
2. Gmail fetch by label
3. raw email archive
4. attachment download
5. PDF extraction
6. normalized parsing
7. local Postgres sync
8. CLI inspection

### Current synced companies
- Birdie
- ConstructAI
- LEASY
- MOX
- NETA AI
- Nuvocargo
- Synthera AI

---

## Current parsing quality

The parser is now useful, but still not production-grade.

### What works reasonably well
- company detection for common patterns
- quarter/month period inference
- body-text parsing
- attachment/PDF text inclusion
- extraction of several financial and operational metrics

### Metrics currently extracted when present
- cash
- monthly burn
- runway months
- revenue progression
- ARR
- net revenue mentions
- annual revenue ranges
- gross profit ranges
- EBITDA expectations
- active clients
- loads moved in month 1
- new engineers hired
- gross margin increase %
- cost-to-serve reduction %
- AI-sourced shipments %
- EBITDA per load increase %

### Known limitations
- some metrics are still low-confidence or overly literal
- some PDF/deck layouts will need bespoke parsing rules
- some section extraction is still too naive
- company-specific KPI normalization is still incomplete
- multi-country KPI deck parsing needs more work

---

## Recommended next development priorities

## Priority 1 — Improve parser precision

### Why
The current store is only as good as the parsed output.

### Focus areas
- improve confidence of extracted metrics
- reduce false positives
- improve distinction between:
  - company-level KPIs
  - anecdotal examples
  - customer-specific case study metrics
- improve extraction from KPI decks and tables
- improve LEASY-style operational KPI parsing

### Planned additions
- source snippets for extracted metrics
- confidence metadata per metric
- better handling of percentages and paired values
- country/segment-specific metric blocks

---

## Priority 2 — Better PDF/deck parsing

### Why
Some of the highest-value updates are in attached decks.

### Focus areas
- KPI pages
- tabular metrics
- financial summary slides
- operational metrics pages
- fundraising/debt/deployment sections

### Likely examples to support
- ARR
- team size
- new contracts
- pre-approved capital
- drawn capital
- collections
- down payment
- customer cycle
- contracts signed / cars delivered
- market-level metrics by geography

---

## Priority 3 — Incremental sync

### Goal
Make the system update only new labeled emails instead of reprocessing everything.

### Deliverables
- last synced state
- idempotent upsert behavior
- fetch only new messages
- safer reruns

---

## Priority 4 — Review and QA workflow

### Goal
Let you inspect and correct parsed outputs before trusting them operationally.

### Potential features
- mark records as reviewed
- store manual overrides
- compare raw source vs parsed record
- flag low-confidence metrics

---

## Priority 5 — Remote Postgres migration

### Goal
Move from local dev DB to remote production Postgres once parsing quality is stable.

### Why later
The parser and schema should stabilize locally before productionizing.

### Migration target
- remote Postgres / managed Postgres
- same or nearly same schema
- keep raw local files or move source archive to object storage later

---

## Priority 6 — Application / analysis layer

Once ingestion and parsing are reliable, build higher-level workflows:
- compare companies
- compare periods for one company
- trend metrics over time
- identify red flags across portfolio companies
- query for funding/risk/runway signals
- portfolio reporting and memo generation

---

## Immediate recommended next step

### Best next build item
Improve extraction specifically for PDF/KPI-style updates.

### Why
The ingestion and storage layers are already working. The biggest leverage now is improving the parser against real portfolio updates so the structured records become decision-useful.

---

## Operating principle

Keep the source of truth layered:

1. **Raw Gmail message + attachments**
2. **Normalized parsed JSON output**
3. **Postgres records for querying and comparison**

Never rely only on the parsed layer when the raw source exists.

That makes the system auditable, debuggable, and safe to improve over time.
