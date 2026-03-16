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
Cleaner than before, but:
- “looking ahead” content is still being treated more like risks than forward plan

### 4. Vertebra thread-style structure
Safe now, but still underparsed:
- sections mostly suppressed instead of intelligently extracted
- period still null
- reply/thread formatting needs dedicated handling

## Best next tasks
Most valuable next work:
1. AltScore structure-aware section parsing
2. Shippify appendix/audit suppression
3. Vertebra thread/reply cleanup
4. optional: improve Aloja forward-looking section classification

## Relevant commits
- `3636c41` — `Improve parser precision heuristics`
- `6f42ecc` — `Improve parser normalization for new startup update samples`
- `6c911d5` — `Tighten section cleanup for forwarded investor updates`

## Suggested restart prompt
Use this in a fresh session:

> Continue work on `lpupdate` in `/home/frivera/.openclaw/workspace/projects/lpupdate`. Latest relevant commits are `6c911d5`, `6f42ecc`, and `3636c41`. The parser metrics are much better, but section extraction still needs work, especially for AltScore asks and Shippify audit-appendix contamination. Focus on `src/lpupdate/parse_updates.py`.
