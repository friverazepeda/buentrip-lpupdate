# Architecture Current State

This document describes what is in the repo today, what is actively used, and what appears experimental.

## Source-of-Truth Directories

Current source-of-truth project layout:

- `config/` - Django project configuration module
- `frontend/` - Next.js frontend application
- `scripts/` - standalone utility/maintenance scripts
- `src/` - core pipeline/runtime Python package (`lpupdate`)
- `dashboard/` - Django app (models/views/admin/templates)
- `docs/` - documentation and migration notes

## 1) What runs in `src/lpupdate`

`src/lpupdate` is the Python ingestion + parsing + sync + report generation pipeline.

Main responsibilities:

- **Ingestion:** fetches investor updates from Gmail (`gmail-fetch`) and Fathom (`fathom-fetch`).
- **Normalization:** stores raw payloads and attachments under `data/`.
- **Parsing:** parses raw inputs with provider modes in `src/lpupdate/parsers/`:
  - `rules` (local deterministic),
  - `bem` (remote provider),
  - `hybrid` (combination/fallback behavior).
- **Persistence:** syncs parsed updates into Postgres (`sync-postgres`) using schema in `src/lpupdate/schema.py`.
- **Reporting output:** generates static report HTML into `reports/` (`generate-report`).

Primary entrypoint:

- CLI module `src/lpupdate/cli.py`
- Script alias in `pyproject.toml`: `lpupdate = "lpupdate.cli:main"`

Core run path used in docs/status:

1. `gmail-fetch` / `fathom-fetch`
2. `parse-raw`
3. `db-apply` + `sync-postgres`
4. `generate-report`

## 2) What `dashboard/` is for

`dashboard/` is a Django app for browsing portfolio/startup/report data and managing records via Django Admin.

From the files:

- `dashboard/models.py` defines data models such as `Vehicle`, `Startup`, `StartupUpdate`, `StartupMetric`, and `QuarterlyLPReport`.
- `dashboard/views.py` provides basic pages:
  - index page with startups/vehicles,
  - startup detail page,
  - report detail page.
- `dashboard/urls.py` maps those views.
- `dashboard/admin.py` and `templates/` support admin/UI rendering.

Django project URL config is in `config/urls.py` (project module). It mounts:

- `dashboard.urls` at `/`,
- Django admin at `/admin/`,
- and serves files under `reports/` as a catch-all route.

## 3) What `web/` currently contains

`web/` currently contains frontend leftovers/build artifacts. The active frontend app now lives in `frontend/`.

1. **Django project module files** (Python):
   - `config/settings.py`, `config/urls.py`, `config/asgi.py`, `config/wsgi.py`, `config/__init__.py`

2. **Next.js frontend app files** (TypeScript/Node):
   - `frontend/package.json` (scripts: `dev`, `build`, `start`, `lint`)
   - `frontend/next.config.ts` (`output: "export"`, `trailingSlash: true`)
   - `frontend/app/**` pages/layout
   - `frontend/components/**`, `frontend/lib/**`
   - `frontend/public/reports/**` sample JSON contracts for the static site

Current split:

- Django project package is `config` (used by `manage.py` as `DJANGO_SETTINGS_MODULE=config.settings`).
- Next.js app root is `frontend/`.

## 4) Production vs experimental (current best read)

Based on `README.md`, `docs/status.md`, and code wiring:

- **Production-like / actively used today**
  - `src/lpupdate` CLI pipeline (Gmail/Fathom fetch, parse, Postgres sync, report generation)
  - Django app in `dashboard/` + Django project wiring in `config/*.py`
  - Generated static report output under `reports/` served by Django catch-all route

- **Experimental / in-progress**
  - BEM and hybrid parsing provider workflows (`bem`, `hybrid`, `bem-sample-run`)
  - New Next.js static frontend under `frontend/app` and related TS files
  - Any manually staged sample data in `frontend/public/reports/`

This classification matches the docs language ("development-stage", "in progress") and the fact that Django routes are still wired to serve `reports/` directly.

## 5) Commands used to run each part

## Pipeline (`src/lpupdate`)

From repo root (examples as documented in repo):

```bash
PYTHONPATH=src /home/frivera/.venvs/gmail-fetch/bin/python -m lpupdate.cli doctor
PYTHONPATH=src /home/frivera/.venvs/gmail-fetch/bin/python -m lpupdate.cli gmail-auth
PYTHONPATH=src /home/frivera/.venvs/gmail-fetch/bin/python -m lpupdate.cli gmail-check
PYTHONPATH=src /home/frivera/.venvs/gmail-fetch/bin/python -m lpupdate.cli gmail-fetch --limit 50
PYTHONPATH=src /home/frivera/.venvs/gmail-fetch/bin/python -m lpupdate.cli fathom-fetch --limit 10
PYTHONPATH=src /home/frivera/.venvs/gmail-fetch/bin/python -m lpupdate.cli parse-raw --limit 50 --source all
PYTHONPATH=src /home/frivera/.venvs/gmail-fetch/bin/python -m lpupdate.cli db-apply
PYTHONPATH=src /home/frivera/.venvs/gmail-fetch/bin/python -m lpupdate.cli sync-postgres --limit 50
PYTHONPATH=src /home/frivera/.venvs/gmail-fetch/bin/python -m lpupdate.cli generate-report
```

Optional consolidated run:

```bash
PYTHONPATH=src /home/frivera/.venvs/gmail-fetch/bin/python -m lpupdate.cli run-pipeline --limit 50 --provider hybrid
```

## Django dashboard (`dashboard/` + `config/*.py`)

```bash
PYTHONPATH=src /home/frivera/.venvs/gmail-fetch/bin/python manage.py migrate
PYTHONPATH=src /home/frivera/.venvs/gmail-fetch/bin/python manage.py runserver
```

Useful admin flow:

```bash
PYTHONPATH=src /home/frivera/.venvs/gmail-fetch/bin/python manage.py createsuperuser
```

## Next.js frontend (`frontend/` app files)

Run inside `frontend/`:

```bash
npm install
npm run dev
npm run build
npm run start
npm run lint
```

Because `next.config.ts` sets `output: "export"`, static export output is generated at build time.

