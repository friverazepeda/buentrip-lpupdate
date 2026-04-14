# buentrip-lpupdate

A development-stage pipeline for ingesting startup investor updates from Gmail, extracting flexible metrics from email bodies and PDF attachments, and storing normalized records in Postgres for analysis.

## What it does

- connects to Gmail via OAuth and pulls reports from Fathom using the canonical list of startups
- fetches emails labeled `Investor/Quarterly`
- saves raw email and Fathom JSON locally
- downloads attachments
- extracts text from PDF attachments
- parses content with regex AND bem for best results
- syncs parsed records into a Django-backed Postgres database
- provides CLI commands to inspect companies, updates, and metrics, and a Django admin UI

## Current architecture

### Sources
- Gmail label: `Investor/Quarterly`
- Fathom AI meeting summaries
- Uses the canonical list of startups to map and filter inputs
- email body text / HTML
- PDF attachments

### Parsing providers
- `rules` — current deterministic parser in `src/lpupdate/parse_updates.py`
- `bem` — remote structured extraction provider scaffold
- `hybrid` — prefers bem output, falls back to/merges with rules

### Local storage
- raw emails: `data/raw_gmail/`
- attachments: `data/attachments/`
- parsed updates: `data/parsed_updates/`

### Database & Back-end
- Django (backend framework and ORM)
- Postgres
- flexible schema using Django models plus JSONFields

Main models/tables:
- `Startup` (canonical list)
- `EmailMessage`
- `StartupUpdate` (normalized from Quarterly/Fathom)
- `Attachment`

## Cursor / AI Tool Context
If you are Cursor or another AI assistant, note:
1. **Sources:** We pull reports from Gmail AND Fathom using the canonical list of startups.
2. **Parsing:** We parse content with regex AND bem to achieve the best extraction results.
3. **Backend:** We use Django for the back-end (ORM, models, admin interface, migrations).
4. **Project Structure:** `src/lpupdate/` holds core Python logic (CLI, parsers, fetchers); `dashboard/` holds the Django app; `data/` holds raw fetched json.
5. **Virtual Env:** The primary env is usually `/home/frivera/.venvs/gmail-fetch/bin/python` with `PYTHONPATH=src`.

## Why JSONB

Investor updates are messy and inconsistent:
- companies report different metrics
- the same company changes metrics over time
- some updates are narrative-heavy
- others come as KPI decks or PDFs

Postgres + JSONB gives enough structure for querying without forcing a brittle fixed schema.

## Requirements

- Python 3.11+
- Gmail OAuth client secret
- Gmail OAuth token
- Postgres

## Environment

Create `.env` in the project root.

Example:

```bash
GOOGLE_OAUTH_CLIENT_SECRET_FILE=/home/frivera/.config/gws/client_secret.json
GOOGLE_OAUTH_TOKEN_FILE=/home/frivera/.config/gws/gmail_token.json
GMAIL_QUERY=label:"Investor/Quarterly"
LPUPDATE_DATABASE_URL=postgresql://lpupdate:lpupdate_dev_password@localhost:5432/lpupdate
LPUPDATE_PARSE_PROVIDER=rules
BEM_API_URL=https://api.bem.ai/YOUR_WORKFLOW_ENDPOINT
BEM_API_KEY=your_bem_api_key
LPUPDATE_BEM_TIMEOUT_SECONDS=60
```

## CLI commands

From the project root:

```bash
cd ~/.openclaw/workspace/projects/lpupdate
PYTHONPATH=src /home/frivera/.venvs/gmail-fetch/bin/python -m lpupdate.cli <command>
```

### Auth and Gmail

```bash
... -m lpupdate.cli doctor
... -m lpupdate.cli gmail-auth
... -m lpupdate.cli gmail-check
... -m lpupdate.cli gmail-fetch --limit 10
```

### Parsing and DB sync

```bash
... -m lpupdate.cli parse-raw --limit 20
... -m lpupdate.cli db-apply
... -m lpupdate.cli sync-postgres --limit 20
```

Provider selection currently happens through `.env`:

```bash
LPUPDATE_PARSE_PROVIDER=rules   # deterministic local parser
LPUPDATE_PARSE_PROVIDER=bem     # remote bem extraction scaffold
LPUPDATE_PARSE_PROVIDER=hybrid  # bem first, rules fallback/merge
```

### Inspection

```bash
... -m lpupdate.cli list-updates --limit 20
... -m lpupdate.cli show-update 7
... -m lpupdate.cli list-companies
... -m lpupdate.cli show-company Nuvocargo
... -m lpupdate.cli company-metrics Nuvocargo
... -m lpupdate.cli show-raw-email <gmail_message_id>
... -m lpupdate.cli show-attachment-text <gmail_message_id> --max-chars 5000
```

## Suggested development flow

1. authenticate Gmail
2. fetch labeled emails
3. parse raw emails and PDF text
4. sync to local Postgres
5. inspect parsed output
6. improve parser quality
7. later migrate to remote Postgres for production

## Current status

Working locally:
- Gmail OAuth
- label-based fetch
- raw email archive
- attachment download
- PDF extraction
- first-pass parsing
- local Postgres sync
- CLI inspection

In progress:
- better metric precision
- better PDF/KPI deck parsing
- incremental sync
- review / QA workflow

## Project documentation

For the fuller roadmap, see:
- `PROJECT_PLAN.md`

## Notes

This is currently a development repo. Raw source preservation is intentional: the parsed layer should never be treated as the only source of truth when original emails and attachments exist.
