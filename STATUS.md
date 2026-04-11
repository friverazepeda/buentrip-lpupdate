# lpupdate status

## Project purpose
Pipeline to:
1. fetch startup investor updates from Gmail
2. parse email bodies + attachments into normalized JSON
3. sync into Postgres
4. generate a static report site with an index + one page per startup

Project path:
`/home/frivera/.openclaw/workspace/projects/lpupdate`

## Current working flow
From project root:

```bash
cd /home/frivera/.openclaw/workspace/projects/lpupdate
PYTHONPATH=src /home/frivera/.venvs/gmail-fetch/bin/python -m lpupdate.cli gmail-fetch --limit 50
PYTHONPATH=src /home/frivera/.venvs/gmail-fetch/bin/python -m lpupdate.cli parse-raw --limit 50
PYTHONPATH=src /home/frivera/.venvs/gmail-fetch/bin/python -m lpupdate.cli sync-postgres --limit 50
PYTHONPATH=src /home/frivera/.venvs/gmail-fetch/bin/python -m lpupdate.cli generate-report
```

## Useful commands

### Show company report
```bash
PYTHONPATH=src /home/frivera/.venvs/gmail-fetch/bin/python -m lpupdate.cli show-company "MOX"
PYTHONPATH=src /home/frivera/.venvs/gmail-fetch/bin/python -m lpupdate.cli show-company "LEASY"
PYTHONPATH=src /home/frivera/.venvs/gmail-fetch/bin/python -m lpupdate.cli show-company "AltScore"
```

### Generate static site
```bash
PYTHONPATH=src /home/frivera/.venvs/gmail-fetch/bin/python -m lpupdate.cli generate-report
```

### BEM sample harness
```bash
LPUPDATE_PARSE_PROVIDER=bem lpupdate bem-sample-run
LPUPDATE_PARSE_PROVIDER=hybrid lpupdate bem-sample-run --provider hybrid
```

## Parser progress

### Core improvements already done
Main parser file:
`src/lpupdate/parse_updates.py`

Implemented:
- `confidence_json` per extracted metric
- better false-positive control
- fixed signature stripping so forwarded email signatures do not wipe attachment text
- added KPI deck extraction for LEASY-style updates
- improved labeled-line parsing for updates like MOX
- prevented Nuvocargo customer-example metrics from being misread as company KPIs

### New sample batch incorporated
Additional startup updates used to improve parsing:
- AltScore
- Shippify
- Vertebra
- PayMon
- Aloja

### Improvements from the new sample batch
Added/fixed:
- better company detection for AltScore, Shippify, Vertebra
- safer period inference
- removed fake period hallucinations like `Q2 2016`
- extraction for headline KPI formats such as:
  - Gross Revenue
  - EBITDA
  - December Revenue
  - Total Revenue 2025
  - GMV 2025
  - Cash on Hand
  - Total ARR EoQ
  - Total Quarterly Revenue
  - Burn Multiple
  - NDR
  - PMF score
  - bookings
  - demo conversion %

### Section-cleanup pass completed
Added cleanup to reduce:
- tracker URLs
- `[image: ...]` junk
- Paperstreet footer/unsubscribe noise
- quoted-thread markers
- small garbage lines
- duplicated section items

## BEM provider status
- `BemParseProvider` now posts to the v2 `/calls` endpoint, injects `bem_schema.json`, and normalizes multiple metrics/contact blocks.
- `BEM_WORKFLOW_NAME` selects the workflow slug (`btv_lpupdate_extraction_gpu0nlg` in `.env`), payload text is base64-encoded per BEM’s contract, and the provider polls `/v2/calls/{callID}` until the workflow outputs `transformedContent`.
- `lpupdate bem-sample-run` executes any provider on the curated Gmail IDs under `samples/bem_eval_samples.json` and saves outputs to `data/provider_samples/<provider>/`.
- Use the harness to compare bem vs hybrid vs rules before enabling hybrid in production.

## Sample-specific status

### LEASY
Now parses deck KPIs including:
- ARR
- cash
- pre-approved capital
- drawn capital
- new contracts
- team size
- avg down payment
- time to evaluate
- time to deliver car
- customer cycle

### MOX
Clean and usable.
Metrics include:
- active clients
- cash
- monthly burn
- runway
- churn
- CAC inbound
- ROAS

### Nuvocargo
No longer incorrectly pulls anecdotal pilot ARR as company ARR.

### PayMon
Now parses:
- December revenue
- Revenue 2025
- GMV 2025
- cash on hand

### Shippify
Now parses:
- gross revenue
- EBITDA
- MRR

### AltScore
Now parses:
- ARR
- quarterly revenue
- runway
- burn multiple
- borrowers enabled/month
- NDR
- PMF score

### Aloja
Now recognized correctly and parses:
- Q4 2025
- bookings
- Extracting 6 metrics, 1 highlight, 1 ask, and 1 risk successfully (as of recent test `crisp-lo` on msg `19cf27a5961737e9`).

### Vertebra
Company detection fixed.
No fake quarter anymore.
Keeps at least:
- MRR
- ARR

## Remaining issues

### 1. AltScore section extraction
Metrics are good, highlights are decent, but:
- `asks_json` is still wrong
- newsletter/repeated layout causes achievements to bleed into asks

### 2. Shippify appendix contamination
Highlights are decent, metrics are good, but:
- audit appendix / supporting documentation text still leaks into `risks_json`

### 3. Aloja section semantics
Recent test on `19cf27a5961737e9` successfully parsed 1 highlight, 1 ask, and 1 risk, up from 0.
- Needs verification if the extracted risk is valid or if “looking ahead” content is still misclassified as a risk.

### 4. Vertebra thread-style structure
Safe now, but still underparsed:
- sections mostly suppressed instead of intelligently extracted
- period still null
- reply/thread formatting needs dedicated handling

## Best next tasks
Most valuable next work:
1. Run `lpupdate bem-sample-run` for `bem` and `hybrid`, compare outputs vs `rules`, and log schema / metric gaps.
2. AltScore structure-aware section parsing
3. Shippify appendix/audit suppression
4. Vertebra thread/reply cleanup
5. optional: verify Aloja forward-looking section classification after recent extraction update.

## Relevant commits
- `3636c41` — `Improve parser precision heuristics`
- `6f42ecc` — `Improve parser normalization for new startup update samples`
- `6c911d5` — `Tighten section cleanup for forwarded investor updates`

## Suggested restart prompt
Use this in a fresh session:

> Continue work on `lpupdate` in `/home/frivera/.openclaw/workspace/projects/lpupdate`. Latest relevant commits are `6c911d5`, `6f42ecc`, and `3636c41`. The parser metrics are much better, but section extraction still needs work, especially for AltScore asks and Shippify audit-appendix contamination. Focus on `src/lpupdate/parse_updates.py`.

## Follow-up note
Leave this for later:
- revisit SecretRef cleanup related to OpenClaw/project secrets and Gmail handling
- current state: core OpenClaw secrets were moved to env-backed SecretRefs, but the Gmail env file was intentionally left as-is
- Gmail env file path: `/home/frivera/.openclaw/env/gmail-ai`
- later decision needed: whether `lpupdate` should keep using a separate Gmail/env workflow or be wired into native OpenClaw `hooks.gmail`
