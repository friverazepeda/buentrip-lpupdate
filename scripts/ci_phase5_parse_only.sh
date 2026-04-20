#!/usr/bin/env bash
# Phase 5 (A.2): offline parse + artifact verification without Postgres.
# Run from the repository root. Requires PYTHONPATH=src (set below).
#
# Usage:
#   ./scripts/ci_phase5_parse_only.sh           # use existing data/ if present
#   ./scripts/ci_phase5_parse_only.sh --clean   # remove data/ first (CI / pinned runs)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ "${1:-}" == "--clean" ]]; then
  rm -rf "${ROOT}/data"
fi

export PYTHONPATH="${ROOT}/src"
export LPUPDATE_PARSE_PROVIDER="${LPUPDATE_PARSE_PROVIDER:-rules}"

python3 scripts/verify_ingestion_rollout.py bootstrap --repo-root "${ROOT}"
python3 -m lpupdate.cli parse-raw --source all --limit 0
python3 scripts/verify_ingestion_rollout.py check --data-root "${ROOT}" --parse-only

echo "Phase 5 parse-only verification: OK"
