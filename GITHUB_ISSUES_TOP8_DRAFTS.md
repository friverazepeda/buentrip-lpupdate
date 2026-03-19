# lpupdate — polished GitHub issue drafts

These are copy-paste-ready drafts for the top 8 issues to tackle over the next few weeks.

---

## 1) Fix AltScore asks extraction

**Title**
Fix AltScore asks extraction in newsletter-style investor updates

**Labels**
`parser`, `qa`, `high-priority`

**Body**
### Summary
AltScore metrics are parsing reasonably well, but `asks_json` is still unreliable. Repeated newsletter-style layout and section bleed are causing achievements/highlights to be misclassified as asks.

### Why this matters
The parser is already good enough to be useful for metrics, but section-level trust still depends on getting asks/highlights/risks right. AltScore is a good sample for this because it exposes one of the current structural weaknesses in section parsing.

### Goal
Make section extraction structure-aware enough to cleanly separate asks from highlights and repeated layout noise in the AltScore sample.

### Scope
- inspect the current AltScore raw email and parsed output
- identify the repeated layout / newsletter markers that cause section bleed
- improve section-boundary detection in the parser
- prevent repeated/boilerplate content from being classified as asks
- validate behavior against the current AltScore sample

### Acceptance criteria
- `asks_json` contains only plausible asks/action requests
- achievements/highlights no longer leak into asks
- obvious newsletter/repeated layout boilerplate does not appear in asks
- a regression check or fixture assertion is added for the AltScore sample

### Implementation notes
Most likely touchpoint:
- `src/lpupdate/parse_updates.py`

### Tasks
- [ ] inspect AltScore raw source and current parsed output
- [ ] identify layout markers causing section bleed
- [ ] update parsing heuristics for asks extraction
- [ ] validate output manually on AltScore sample
- [ ] add regression coverage

---

## 2) Suppress Shippify appendix / audit contamination

**Title**
Suppress appendix and audit-document contamination in Shippify risks extraction

**Labels**
`parser`, `qa`, `high-priority`

**Body**
### Summary
Shippify metrics are useful, but supporting documentation / appendix text is still leaking into `risks_json`. This makes the output noisier than it should be and reduces trust in section-level extraction.

### Why this matters
Appendix and audit-support material often contains operational or descriptive language that looks risk-like without actually being part of the core investor update. We need to isolate the update itself from supporting documents.

### Goal
Filter or downweight appendix-like content so only core investor update material contributes to `risks_json` and other sections.

### Scope
- inspect Shippify raw source and parsed section outputs
- identify appendix / audit markers and structural signatures
- suppress or isolate non-core supporting text
- preserve real risks while excluding documentation noise
- add regression protection for the current sample

### Acceptance criteria
- appendix/supporting text no longer appears in `risks_json`
- Shippify highlights/risks are materially cleaner
- parser still retains relevant business-risk content
- a regression check or fixture assertion is added

### Implementation notes
Most likely touchpoint:
- `src/lpupdate/parse_updates.py`

### Tasks
- [ ] inspect Shippify raw source and parsed output
- [ ] identify appendix/audit contamination markers
- [ ] update suppression / filtering heuristics
- [ ] manually verify Shippify risks output
- [ ] add regression coverage

---

## 3) Improve Vertebra thread/reply parsing

**Title**
Improve parsing for thread-style / reply-chain investor updates (Vertebra sample)

**Labels**
`parser`, `qa`, `high-priority`

**Body**
### Summary
Vertebra is safer than before, but still underparsed. The thread/reply structure causes weak section extraction, and the reporting period is still null.

### Why this matters
Thread-style forwarded updates are common and structurally different from cleaner newsletter or deck formats. We need a reliable strategy for extracting useful signals from reply chains without overfitting to one sample.

### Goal
Handle thread-style forwarded/replied investor updates more intelligently, using Vertebra as the primary sample.

### Scope
- improve cleanup for quoted-thread markers and reply-chain formatting
- improve period inference when evidence exists in thread-style content
- recover useful highlights/asks/risks without pulling in junk from quoted history
- preserve conservative behavior when the source is ambiguous

### Acceptance criteria
- quoted reply junk is materially reduced
- period is inferred when supported by the source
- section extraction is better than the current mostly-suppressed behavior
- a regression check or fixture assertion is added for Vertebra

### Implementation notes
Primary touchpoint:
- `src/lpupdate/parse_updates.py`

### Tasks
- [ ] inspect Vertebra raw source and parsed output
- [ ] improve quoted-thread cleanup
- [ ] improve period inference for reply-chain structure
- [ ] validate section extraction behavior manually
- [ ] add regression coverage

---

## 4) Add parser regression fixtures for current startup sample set

**Title**
Add parser regression fixtures for current representative startup samples

**Labels**
`parser`, `qa`, `high-priority`

**Body**
### Summary
Parser quality is improving quickly, but changes remain risky without fixture-based regression coverage.

### Why this matters
The parser now supports several distinct startup update formats, including forwarded emails, KPI decks, newsletters, and thread-style updates. We need a lightweight way to prevent regressions as heuristics keep evolving.

### Goal
Create a representative regression suite that checks key parser outputs for the current startup sample set.

### Initial sample set
- AltScore
- Shippify
- Vertebra
- PayMon
- Aloja
- LEASY
- MOX
- Nuvocargo

### Scope
- choose a lightweight fixture/assertion approach
- encode a small set of expected outputs per sample
- focus on high-signal checks: company, period, critical metrics, and known failure cases
- document how to run the regression suite

### Acceptance criteria
- parser changes can be validated automatically against representative samples
- known-good extractions and known prior bugs are encoded in checks
- running the regression checks is documented and straightforward

### Tasks
- [ ] choose fixture/assertion approach
- [ ] add representative sample coverage
- [ ] encode expected outputs for each sample
- [ ] add checks for prior bug cases
- [ ] document how to run the suite

---

## 5) Add source excerpts for extracted metrics and sections

**Title**
Add source excerpts to parsed metrics and section items for auditability

**Labels**
`parser`, `data-model`, `high-priority`

**Body**
### Summary
It is still too hard to validate where parsed metrics and section items came from. We should attach source snippets to extracted content so the output is more auditable.

### Why this matters
Raw source preservation is already a core principle of the project. The next step is making parsed outputs traceable back to source text so review and correction are much faster.

### Goal
Attach source excerpts to parsed metrics and, where practical, section items such as highlights, asks, and risks.

### Scope
- define a simple source excerpt shape for canonical parsed output
- start with metrics first
- extend to section items if practical in the same iteration
- preserve backward compatibility as much as possible

### Acceptance criteria
- each extracted metric includes a source snippet or excerpt
- source excerpt is sufficient for quick human validation
- the parsed output format is documented clearly enough for downstream use

### Notes
This issue pairs well with future review/QA work and any hybrid/BEM evaluation.

### Tasks
- [ ] define source excerpt format
- [ ] add source excerpts to metric extraction
- [ ] extend to section items if practical
- [ ] validate output on representative samples
- [ ] document the new parsed shape

---

## 6) Implement incremental Gmail fetch / sync state

**Title**
Implement incremental Gmail fetch and persisted sync state

**Labels**
`pipeline`, `infra`, `high-priority`

**Body**
### Summary
The current workflow is still batch-oriented. It works, but it reprocesses more than necessary and does not yet behave like a regular operational ingestion pipeline.

### Why this matters
As the labeled update volume grows, the default path should fetch and process only new messages while remaining safe to rerun.

### Goal
Persist sync state so the default pipeline only fetches and processes new labeled Gmail messages.

### Scope
- define a durable sync-state mechanism
- fetch only newer or missing messages by default
- preserve safe reruns and recovery behavior
- document how to force a full rescan when needed

### Acceptance criteria
- default fetch path only processes new messages
- sync state is persisted clearly and safely
- reruns are idempotent
- recovery/reset path is documented

### Implementation notes
Likely touchpoints:
- Gmail fetch logic
- local state storage
- CLI behavior / docs

### Tasks
- [ ] define sync-state storage approach
- [ ] update Gmail fetch logic to use state
- [ ] ensure reruns remain safe
- [ ] document full-rescan/reset path
- [ ] test behavior on repeated runs

---

## 7) Add reviewed / needs-review state for parsed updates

**Title**
Add reviewed / needs-review state to parsed updates

**Labels**
`qa`, `data-model`, `report-ui`

**Body**
### Summary
There is currently no explicit distinction between machine-generated parsed output and reviewed/trusted output.

### Why this matters
As the pipeline becomes more useful, we need a lightweight review workflow so parsed records can be treated as either pending review or trusted enough for operational use.

### Goal
Add review state so parsed updates can be marked as `reviewed` or `needs-review`.

### Scope
- define review status model
- store review status in DB and/or local metadata
- expose review state in inspection and reporting flows
- choose sensible defaults for newly parsed records

### Acceptance criteria
- a parsed report can be marked `reviewed` or `needs-review`
- status is queryable and visible in at least one user-facing inspection flow
- new reports default into a sensible review state

### Notes
This is a foundational issue for a later QA/review interface.

### Tasks
- [ ] define review-state model
- [ ] persist review status
- [ ] expose status in inspection/report output
- [ ] define default behavior for new reports
- [ ] document usage

---

## 8) Build raw-vs-parsed review view

**Title**
Build a raw-vs-parsed review view for QA of investor update extraction

**Labels**
`qa`, `report-ui`, `pipeline`

**Body**
### Summary
Reviewing parser quality is still too manual. We need a simple review surface that shows raw source material next to parsed output.

### Why this matters
This is the fastest path to making parser improvements actionable. If review is easy, parser iteration gets faster and trust in the system improves.

### Goal
Create a lightweight review view that compares source content against parsed fields.

### Scope
- show raw email / attachment text alongside parsed output
- focus first on key fields:
  - company
  - period
  - summary
  - metrics
  - highlights
  - asks
  - risks
- optimize for usefulness, not polish

### Acceptance criteria
- reviewer can inspect source and parsed output side-by-side
- the view is usable for spotting extraction mistakes quickly
- initial version supports at least one real QA workflow on current samples

### Notes
A simple local/static or CLI-assisted version is fine as a first pass.

### Tasks
- [ ] define first-pass review workflow
- [ ] choose implementation approach
- [ ] expose source + parsed output together
- [ ] validate usability on current samples
- [ ] document the workflow

---

## Suggested creation order

1. Fix AltScore asks extraction
2. Suppress Shippify appendix / audit contamination
3. Improve Vertebra thread/reply parsing
4. Add parser regression fixtures for current startup sample set
5. Add source excerpts for extracted metrics and sections
6. Implement incremental Gmail fetch / sync state
7. Add reviewed / needs-review state for parsed updates
8. Build raw-vs-parsed review view
