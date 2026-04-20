---
name: Phase 4 Safe Persistence Plan
overview: "Implement Phase 4 as additive persistence observability: quarantine unsynced parsed records and enrich sync outcomes without changing DB writes, parse contracts, or report generation behavior."
todos:
  - id: phase4-add-quarantine-dir
    content: Add quarantine output directory setup in sync stage.
    status: completed
  - id: phase4-write-unsynced-artifacts
    content: Write one compact JSON artifact for each unsynced parsed record with explicit reason code.
    status: completed
  - id: phase4-link-summary-to-quarantine
    content: Add quarantine metadata (dir/count) to existing run summary without renaming existing keys.
    status: completed
  - id: phase4-preserve-sync-contract
    content: Verify no changes to DB write logic, stdout synced payload shape, or CLI flags.
    status: completed
  - id: phase4-verify-with-sample-run
    content: Run sync on sample data and confirm skip reasons align with quarantine artifacts.
    status: completed
isProject: false
---

# Phase 4 Safe Persistence Plan

## Objective

Add persistence-level auditability for records that do not get written to `quarterly_updates`, while preserving existing sync behavior and outputs.

## Scope (Additive Only)

- Keep existing `upsert_company`, `upsert_email_message`, and `upsert_quarterly_update` call order and return handling unchanged.
- Keep CLI command names/flags unchanged.
- Keep parsed update schema unchanged.
- Add write-only observability artifacts for unsynced records.

## Files to Update

- `[/Users/frivera/git_repos/buentrip-lpupdate/src/lpupdate/cli.py](/Users/frivera/git_repos/buentrip-lpupdate/src/lpupdate/cli.py)`
- (Optional tests) `[/Users/frivera/git_repos/buentrip-lpupdate/src/lpupdate/tests/test_sync_observability.py](/Users/frivera/git_repos/buentrip-lpupdate/src/lpupdate/tests/test_sync_observability.py)`

## Implementation Steps

### 1) Add quarantine output location in `cmd_sync_postgres`

- Create a directory with `ensure_data_dir("data/quarantine_unsynced")`.
- Use one JSON file per unsynced parsed record, keyed by parsed filename (or message id), to avoid changing current output locations.

### 2) Emit structured quarantine records when sync skips

For each parsed file where `update_id is None`, write a compact record with:

- `gmail_message_id`
- `source_path` (parsed file)
- `raw_source_path` (if known)
- `company_name`
- `reason_code`
- `reason_detail` (small string)
- `synced`: `false`
- `generated_at_epoch_ms`

Reason code mapping (additive, explicit):

- `raw_source_missing`
- `no_company_match`
- `empty_content`
- `not_persisted`

### 3) Keep run summary as source of truth for counts

- Continue updating existing `summary["skipped"]` and `skip_reasons`.
- Add one extra summary field: `quarantine_dir` and optional `quarantined_count`.
- Do not remove or rename existing summary keys.

### 4) Ensure no DB behavior changes

- Do not alter SQL.
- Do not alter conditions for when `upsert_quarterly_update` returns `None`.
- Do not alter existing `synced` payload format in stdout.

### 5) Add focused tests (if test env supports DB mocking)

- Unit-test helper logic for reason code selection and quarantine payload writing.
- Mock file writes and verify that unsynced cases generate quarantine artifacts.
- Verify synced cases do not create quarantine files.

## Verification Checklist

- Run `lpupdate sync-postgres --source all --limit N` on a known dataset.
- Confirm:
  - Existing stdout `count`/`synced` output remains unchanged in shape.
  - Existing `data/parsed_updates/run_summary.json` still generated with prior keys.
  - New quarantine files appear only for unsynced records.
  - `skip_reasons` aligns with quarantine `reason_code` values.

## Rollout Safety

- Phase 4 is strictly additive and reversible.
- If needed, disable by removing quarantine writes; existing sync path continues to work unchanged.

