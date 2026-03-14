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
