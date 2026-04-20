#!/usr/bin/env python3
"""CLI wrapper for Phase 5 ingestion rollout verification (see docs/ingestion-rollout-phase5.md)."""

from __future__ import annotations

import sys
from pathlib import Path


def _find_src_dir() -> Path:
    """
    Resolve .../src so `import lpupdate` works regardless of where this file lives
    under the repo (e.g. scripts/ or a nested tools path).
    """
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        candidate = parent / "src" / "lpupdate"
        if candidate.is_dir() and (candidate / "__init__.py").is_file():
            return parent / "src"
    raise SystemExit(
        "Could not find src/lpupdate in any parent of this script. "
        "Run from a full repo checkout that contains src/lpupdate/rollout_verify.py."
    )


def _prepend_src() -> None:
    src = _find_src_dir()
    rollout = src / "lpupdate" / "rollout_verify.py"
    if not rollout.is_file():
        raise SystemExit(
            f"Missing {rollout}. Update your checkout (git pull) or restore rollout_verify.py."
        )
    # Prefer repo src over any globally installed older `lpupdate` egg.
    sys.path.insert(0, str(src))


def main() -> int:
    _prepend_src()
    from lpupdate.rollout_verify import main as run

    return run()


if __name__ == "__main__":
    raise SystemExit(main())
