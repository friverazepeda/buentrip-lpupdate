from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from .store import iter_data_record_json_files

QUARANTINE_REASON_CODES = frozenset(
    {"raw_source_missing", "no_company_match", "empty_content", "not_persisted"}
)

# Minimum keys expected on every parsed update JSON (downstream + UI contract).
PARSED_REQUIRED_KEYS = (
    "gmail_message_id",
    "report_period_label",
    "report_quarter",
    "report_year",
    "received_at",
    "summary",
    "metrics_json",
    "highlights_json",
    "asks_json",
    "risks_json",
)

PARSED_TYPED_FIELDS: dict[str, type] = {
    "metrics_json": dict,
    "highlights_json": list,
    "asks_json": list,
    "risks_json": list,
    "people_json": list,
    "confidence_json": dict,
}


def default_repo_root() -> Path:
    """Repository root when this module lives at src/lpupdate/rollout_verify.py."""
    return Path(__file__).resolve().parents[2]


def bootstrap_rollout_sample(repo_root: Path, *, overwrite: bool = False) -> dict[str, list[str]]:
    """
    Copy committed rollout_samples into data/raw_* under repo_root.
    """
    copied: list[str] = []
    skipped: list[str] = []
    for sub in ("raw_gmail", "raw_fathom"):
        src_dir = repo_root / "rollout_samples" / sub
        if not src_dir.is_dir():
            continue
        dst_dir = repo_root / "data" / sub
        dst_dir.mkdir(parents=True, exist_ok=True)
        for path in sorted(src_dir.glob("*.json")):
            dest = dst_dir / path.name
            if dest.exists() and not overwrite:
                skipped.append(str(dest))
                continue
            shutil.copy2(path, dest)
            copied.append(str(dest))
    return {"copied": copied, "skipped": skipped}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def verify_parsed_update_file(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = _load_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{path}: invalid JSON ({exc})"]
    if not isinstance(data, dict):
        return [f"{path}: root must be a JSON object"]
    if not data.get("gmail_message_id"):
        errors.append(f"{path}: missing or empty gmail_message_id")
    for key in PARSED_REQUIRED_KEYS:
        if key not in data:
            errors.append(f"{path}: missing key {key!r}")
    for key, expected_type in PARSED_TYPED_FIELDS.items():
        if key not in data:
            continue
        val = data[key]
        if val is None:
            continue
        if not isinstance(val, expected_type):
            errors.append(
                f"{path}: {key} must be {expected_type.__name__} or null, got {type(val).__name__}"
            )
    return errors


def verify_sync_stage_summary(summary: dict[str, Any], data_root: Path) -> list[str]:
    errors: list[str] = []
    if summary.get("stage") != "sync_postgres":
        errors.append(f"parsed_updates/run_summary.json: stage is {summary.get('stage')!r}, expected 'sync_postgres'")
        return errors

    skipped = int(summary.get("skipped") or 0)
    skip_reasons = summary.get("skip_reasons") or {}
    if not isinstance(skip_reasons, dict):
        errors.append("skip_reasons must be an object")
        return errors

    reason_sum = sum(int(v) for v in skip_reasons.values() if isinstance(v, (int, float)))
    if reason_sum != skipped:
        errors.append(f"skip_reasons values sum to {reason_sum}, but skipped={skipped}")

    quarantined = int(summary.get("quarantined_count") or 0)
    if quarantined != skipped:
        errors.append(f"quarantined_count={quarantined} != skipped={skipped}")

    qdir = summary.get("quarantine_dir")
    if qdir:
        qpath = Path(qdir)
        if not qpath.is_absolute():
            qpath = data_root / qpath
        if qpath.is_dir():
            on_disk = len(list(qpath.glob("*.json")))
            if on_disk != quarantined:
                errors.append(f"quarantine_dir has {on_disk} json files, quarantined_count={quarantined}")
            for fp in qpath.glob("*.json"):
                try:
                    rec = _load_json(fp)
                except (OSError, json.JSONDecodeError) as exc:
                    errors.append(f"{fp}: invalid quarantine JSON ({exc})")
                    continue
                code = rec.get("reason_code")
                if code not in QUARANTINE_REASON_CODES:
                    errors.append(f"{fp}: unknown reason_code {code!r}")
        else:
            errors.append(f"quarantine_dir does not exist: {qpath}")

    parsed_examined = int(summary.get("parsed") or 0)
    if parsed_examined and quarantined <= parsed_examined:
        # Invariant from cmd_sync_postgres: each file is either synced or skipped once.
        pass  # len(synced) not stored in summary; skip strict equality check

    return errors


def verify_parse_stage_summary(summary: dict[str, Any], parsed_dir: Path) -> list[str]:
    errors: list[str] = []
    if summary.get("stage") != "parse_raw":
        errors.append(f"run_summary stage is {summary.get('stage')!r}, expected 'parse_raw'")
        return errors
    parsed_count = int(summary.get("parsed") or 0)
    files = iter_data_record_json_files(parsed_dir)
    if parsed_count != len(files):
        errors.append(f"parse summary parsed={parsed_count} but found {len(files)} parsed JSON files")
    return errors


def verify_rollout_artifacts(data_root: Path, *, require_sync_summary: bool = True) -> list[str]:
    """
    Validate data/ layout after parse and (optionally) sync.

    When require_sync_summary is True, expects data/parsed_updates/run_summary.json
    to describe the sync_postgres stage (last writer after a full sync).
    """
    errors: list[str] = []
    parsed_dir = data_root / "data" / "parsed_updates"
    if not parsed_dir.is_dir():
        return [f"missing directory: {parsed_dir}"]

    summary_path = parsed_dir / "run_summary.json"
    if not summary_path.is_file():
        errors.append(f"missing {summary_path}")
        return errors

    try:
        summary = _load_json(summary_path)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{summary_path}: invalid JSON ({exc})"]

    for path in iter_data_record_json_files(parsed_dir):
        errors.extend(verify_parsed_update_file(path))

    if require_sync_summary:
        errors.extend(verify_sync_stage_summary(summary, data_root))
    else:
        if summary.get("stage") == "parse_raw":
            errors.extend(verify_parse_stage_summary(summary, parsed_dir))
        elif summary.get("stage") == "sync_postgres":
            errors.extend(verify_sync_stage_summary(summary, data_root))
        else:
            errors.append(f"unexpected run_summary stage: {summary.get('stage')!r}")

    return errors


def _cmd_bootstrap(args: argparse.Namespace) -> int:
    root = Path(args.repo_root).expanduser().resolve() if args.repo_root else default_repo_root()
    result = bootstrap_rollout_sample(root, overwrite=args.overwrite)
    print(json.dumps({"repo_root": str(root), **result}, indent=2))
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    root = Path(args.data_root).expanduser().resolve()
    errs = verify_rollout_artifacts(root, require_sync_summary=not args.parse_only)
    if errs:
        print(json.dumps({"ok": False, "errors": errs}, indent=2))
        return 1
    print(json.dumps({"ok": True, "data_root": str(root)}, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Phase 5 rollout: seed offline samples and verify pipeline artifacts.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p0 = sub.add_parser("bootstrap", help="Copy rollout_samples/* into data/raw_*")
    p0.add_argument(
        "--repo-root",
        type=str,
        default=None,
        help="Repository root (default: inferred from package location)",
    )
    p0.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace files that already exist under data/raw_*",
    )
    p0.set_defaults(func=_cmd_bootstrap)

    p1 = sub.add_parser("check", help="Validate parsed JSON + run_summary invariants")
    p1.add_argument(
        "--data-root",
        type=str,
        default=".",
        help="Directory that contains ./data/ (usually the git repo root)",
    )
    p1.add_argument(
        "--parse-only",
        action="store_true",
        help="Allow run_summary from parse_raw (after parse-raw without sync)",
    )
    p1.set_defaults(func=_cmd_check)

    ns = parser.parse_args(argv)
    return int(ns.func(ns))


if __name__ == "__main__":
    raise SystemExit(main())
