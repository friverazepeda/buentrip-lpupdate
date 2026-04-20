from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def ensure_data_dir(base: str | Path = 'data') -> Path:
    path = Path(base)
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: str | Path, payload: Any) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    return out


def iter_data_record_json_files(dir_path: str | Path) -> list[Path]:
    """
    Sorted *.json files under dir_path, excluding run_summary.json.

    Stage summaries are written alongside raw/parsed records; those files must
    never be treated as message/update payloads.
    """
    path = Path(dir_path)
    return sorted(p for p in path.glob("*.json") if p.name != "run_summary.json")
