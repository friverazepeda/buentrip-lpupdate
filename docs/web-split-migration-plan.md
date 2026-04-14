# Web Split Migration Plan

> Historical migration-plan document. It describes the pre-split state and phased migration approach used during the `web/` -> `config/` + `frontend/` transition.

## Summary

The repo currently has a mixed `web/` directory that contains both:

- Django project module files (`settings.py`, `urls.py`, `wsgi.py`, `asgi.py`, `__init__.py`)
- Next.js frontend files (`package.json`, `next.config.ts`, `tsconfig.json`, `eslint.config.mjs`, `app/`, `components/`, `lib/`, `public/`)

Long-term target is feasible with a low-risk staged approach:

1. Extract Django project module to `config/` first (module rename/path update only).
2. Move frontend app to `frontend/` second (filesystem move + frontend tooling/path updates).

This ordering minimizes backend risk while keeping Django and frontend behavior stable during transition.

## Current dependencies on `web/`

## Direct module-path dependencies (`web.settings`, `web.urls`, `web.wsgi`, `web.asgi`)

- `manage.py`
  - `DJANGO_SETTINGS_MODULE='web.settings'`
- `web/wsgi.py`
  - `DJANGO_SETTINGS_MODULE='web.settings'`
- `web/asgi.py`
  - `DJANGO_SETTINGS_MODULE='web.settings'`
- `web/settings.py`
  - `ROOT_URLCONF='web.urls'`
  - `WSGI_APPLICATION='web.wsgi.application'`
- `scripts/load_csv.py`
  - `DJANGO_SETTINGS_MODULE='web.settings'`
- `scripts/migrate_data.py`
  - `DJANGO_SETTINGS_MODULE='web.settings'`

## Deployment/runtime assumptions

- `lpupdate.service`
  - `ExecStart ... gunicorn ... web.wsgi:application`
  - This is the most sensitive deployment dependency in-repo.

## Filesystem/path assumptions that reference `web/`

- Root `.gitignore` includes frontend build/dependency paths:
  - `web/.next/`
  - `web/out/`
  - `web/node_modules/`

These need adjustment when frontend moves to `frontend/`.

## Environment config notes

- `.env.example` does **not** hardcode `web.settings`.
- No explicit `DJANGO_SETTINGS_MODULE` override found there.
- Environment contract appears centered on Gmail/Postgres/parser variables.

## Documentation assumptions

- `README.md` does not currently reference `web.settings` directly.
- Existing docs that discuss architecture can become stale once the split happens (especially any text that describes `web/` as mixed).

## Is `web/` mixed today?

Yes. Current `web/` contains both Django and Next.js concerns:

- Django project config module:
  - `web/settings.py`, `web/urls.py`, `web/wsgi.py`, `web/asgi.py`, `web/__init__.py`
- Next.js frontend app:
  - `web/package.json`, `web/package-lock.json`, `web/next.config.ts`, `web/tsconfig.json`, `web/eslint.config.mjs`
  - `web/app/**`, `web/components/**`, `web/lib/**`, `web/public/**`

This overlap is exactly what the split should resolve.

## Risk areas

1. **Service startup risk (highest)**
   - `lpupdate.service` points to `web.wsgi:application`.
   - If not updated with module extraction, deployment/runtime fails.

2. **Django command/script risk**
   - `manage.py`, `scripts/load_csv.py`, `scripts/migrate_data.py` hardcode `web.settings`.
   - Partial updates can break CLI/admin/maintenance workflows.

3. **Frontend tooling/path risk**
   - Frontend currently rooted in `web/`; moving to `frontend/` affects lockfile, build output ignores, and run instructions.

4. **Docs drift risk**
   - Migration can succeed technically while docs still reference old paths/modules.

5. **Ambiguity to resolve explicitly**
   - `web/lib/` + `web/public/reports/` are frontend-consumed now, but data contracts may conceptually belong to shared domain docs/pipeline.
   - Recommendation: treat as frontend-owned for the move unless a separate shared-package decision is made.

## Recommended migration sequence

## Phase 1 — Extract Django project module to `config/` (no frontend move yet)

Smallest safe backend step:

1. Move Django module files:
   - `web/settings.py` -> `config/settings.py`
   - `web/urls.py` -> `config/urls.py`
   - `web/wsgi.py` -> `config/wsgi.py`
   - `web/asgi.py` -> `config/asgi.py`
   - `web/__init__.py` -> `config/__init__.py`
2. Update required module references only:
   - `manage.py` -> `config.settings`
   - `config/wsgi.py` + `config/asgi.py` -> `config.settings`
   - `config/settings.py`:
     - `ROOT_URLCONF='config.urls'`
     - `WSGI_APPLICATION='config.wsgi.application'`
   - `scripts/load_csv.py` + `scripts/migrate_data.py` -> `config.settings`
   - `lpupdate.service` -> `config.wsgi:application`
3. Do not change business logic.

## Phase 2 — Move frontend app to `frontend/` (after Django module is stable)

1. Move Next.js files/dirs from `web/` to `frontend/`.
2. Update frontend-local config/paths as needed (imports, tooling configs if they assume old root).
3. Update root `.gitignore` frontend path entries from `web/...` to `frontend/...`.
4. Keep backend imports untouched in this phase.

## Phase 3 — Documentation reconciliation

1. Update architecture/runbook docs to the new layout.
2. Confirm all run commands reference the correct locations (`config` for Django module, `frontend` for Next app).

## Validation steps after each future migration phase

## After Phase 1 (Django module extraction)

- `PYTHONPATH=src /home/frivera/.venvs/gmail-fetch/bin/python manage.py check`
- `PYTHONPATH=src /home/frivera/.venvs/gmail-fetch/bin/python manage.py migrate --plan`
- `PYTHONPATH=src /home/frivera/.venvs/gmail-fetch/bin/python manage.py runserver`
- `/home/frivera/.venvs/gmail-fetch/bin/gunicorn --bind 127.0.0.1:8081 config.wsgi:application`
- Optional maintenance scripts:
  - `PYTHONPATH=src /home/frivera/.venvs/gmail-fetch/bin/python scripts/load_csv.py`
  - `PYTHONPATH=src /home/frivera/.venvs/gmail-fetch/bin/python scripts/migrate_data.py`

## After Phase 2 (frontend move)

- `cd frontend && npm install`
- `cd frontend && npm run build`
- `cd frontend && npm run dev`
- Verify rendered routes and static assets load.
- Confirm no backend behavior regression (`manage.py check`, `runserver`).

## After Phase 3 (docs update)

- Search for stale references:
  - `web.settings`, `web.urls`, `web.wsgi`, `web.asgi`
  - frontend run instructions that still point to `web/`
- Ensure operational docs match actual runtime commands.

