# Scripts Migration Plan

Analysis-only proposal for standalone utility/maintenance scripts that could later move into a top-level `scripts/` directory.

## Candidates

## 1) CSV loader utility

1. **Current path**: `load_csv.py`  
2. **Likely purpose**: One-off data loader that reads a portfolio CSV and upserts Django models (`Startup`, `VehicleStartup`) for bootstrap/maintenance tasks.  
3. **Imported anywhere?**: No import references found in repo code; appears to be executed directly via `if __name__ == '__main__':`.  
4. **Risk if moved**: **Medium**  
   - Runtime app should not depend on it.  
   - Risk is mostly operational (existing run commands/docs might still assume root path).  
   - It depends on Django settings and environment assumptions, so command invocation must be updated carefully.  
5. **Recommended new path**: `scripts/load_csv.py`

## 2) Legacy-to-Django migration helper

1. **Current path**: `migrate_data.py`  
2. **Likely purpose**: One-off migration helper that reads legacy tables (`companies`, `quarterly_updates`) and materializes records into Django models (`StartupUpdate`, `StartupMetric`, etc.).  
3. **Imported anywhere?**: No import references found in repo code; appears to be executed directly via `if __name__ == '__main__':`.  
4. **Risk if moved**: **Medium**  
   - Not part of the normal runtime path.  
   - Same operational risk as above: old commands/runbooks may break if path changes are not updated.  
5. **Recommended new path**: `scripts/migrate_data.py`

## 3) Fathom API smoke-test helper

1. **Current path**: `fathom_test.py`  
2. **Likely purpose**: Ad-hoc API test script that calls Fathom recordings endpoint and prints response/error output for debugging credentials/connectivity.  
3. **Imported anywhere?**: No import references found in repo code.  
4. **Risk if moved**: **Low to Medium**  
   - No runtime dependency detected.  
   - It imports `lpupdate.config`; moving it may require adjusted execution environment (`PYTHONPATH=src` or installed package).  
5. **Recommended new path**: `scripts/fathom_test.py`

## Not recommended to move

- `manage.py`  
  Primary Django management entrypoint (`runserver`, `migrate`, admin commands); moving it is higher-risk and not a utility-script cleanup.

- `src/lpupdate/cli.py` and files under `src/lpupdate/`  
  These are application/runtime code and should remain in package structure.

- Deployment config files (for example `lpupdate.service`)  
  Operational config, not standalone maintenance scripts.

## Suggested migration order

1. Move `fathom_test.py` first (lowest coupling).  
2. Move `load_csv.py` second (one-off loader, moderate operational coupling).  
3. Move `migrate_data.py` third (migration helper with highest data-impact if run incorrectly).  
4. After each move, update any docs/run commands that reference old root paths and do a quick invocation smoke test.

