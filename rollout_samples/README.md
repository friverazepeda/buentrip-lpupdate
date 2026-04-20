# Rollout sample raw payloads

Small, committed JSON files used for **Phase 5** offline verification of `parse-raw` → `sync-postgres` without calling Gmail or Fathom.

Filenames must match `gmail_message_id` inside each file (the pipeline names raw and parsed files from that id).

Seed your local `data/` tree from the repo root:

```bash
python3 scripts/verify_ingestion_rollout.py bootstrap
```

Then run parse/sync against `LPUPDATE_PARSE_PROVIDER=rules` (default) and a disposable database URL. See `docs/ingestion-rollout-phase5.md`.
