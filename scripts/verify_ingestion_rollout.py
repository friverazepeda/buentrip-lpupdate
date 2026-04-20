#!/usr/bin/env python3
"""CLI wrapper for Phase 5 ingestion rollout verification (see docs/ingestion-rollout-phase5.md)."""

from __future__ import annotations

import sys
from pathlib import Path


def _prepend_src() -> None:
    root = Path(__file__).resolve().parents[1]
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def main() -> int:
    _prepend_src()
    from lpupdate.rollout_verify import main as run

    return run()


if __name__ == "__main__":
    raise SystemExit(main())
