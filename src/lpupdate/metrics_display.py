"""
Human-readable formatting for parsed metric values before persistence in Django.

`metrics_json` from the rules parser often stores structured dicts (money with
currency/period). `scripts/migrate_data.py` maps rows into `StartupMetric.value`
(CharField). Using Python's default `str(dict)` produces single-quoted reprs;
this module produces stable, readable strings for the JSON API and web UI.
"""

from __future__ import annotations

import json
from typing import Any


def format_metric_value_for_display(value: Any, *, max_len: int = 255) -> str:
    """
    Convert a parsed metric value into a short string suitable for StartupMetric.value.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return value.strip()[:max_len]
    if isinstance(value, int):
        return f"{value:,}"[:max_len]
    if isinstance(value, float):
        if value == int(value):
            return str(int(value))[:max_len]
        return f"{value:.4g}"[:max_len]
    if isinstance(value, dict):
        return _format_dict_metric(value)[:max_len]
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))[:max_len]
    return str(value)[:max_len]


def _format_dict_metric(d: dict[str, Any]) -> str:
    if "value" in d and isinstance(d.get("value"), (int, float)):
        v = float(d["value"])
        currency = (d.get("currency") or "USD").upper()
        period = d.get("period")
        base = _format_money_amount(v, currency)
        if period:
            return f"{base} ({period})"
        return base
    if "value" in d:
        base = str(d.get("value") or "").strip()
        unit = str(d.get("unit") or "").strip()
        period = str(d.get("period") or "").strip()
        if unit and unit.lower() not in base.lower():
            base = f"{base} {unit}".strip()
        if period:
            base = f"{base} ({period})".strip()
        return base
    if "low" in d and "high" in d and isinstance(d["low"], (int, float)) and isinstance(d["high"], (int, float)):
        cur = d.get("currency") or "USD"
        return f"{_format_money_amount(float(d['low']), cur)} – {_format_money_amount(float(d['high']), cur)}"
    if "previous_value" in d and "current_value" in d:
        cur = d.get("currency") or "USD"
        pv, cv = d["previous_value"], d["current_value"]
        if isinstance(pv, (int, float)) and isinstance(cv, (int, float)):
            return f"{_format_money_amount(float(pv), cur)} → {_format_money_amount(float(cv), cur)}"
        return f"{pv} → {cv}"
    # Last-resort human readable mapping (never leak a raw JSON object).
    pairs = [f"{k}: {v}" for k, v in d.items() if v is not None and str(v).strip()]
    return ", ".join(pairs) if pairs else ""


def _format_money_amount(amount: float, currency: str) -> str:
    """Format absolute currency amounts (parser stores expanded dollars, not millions units)."""
    cu = (currency or "USD").upper()
    symbol = "$" if cu in ("USD", "US$") else f"{cu} "
    a = abs(amount)
    if a >= 1_000_000:
        x = amount / 1_000_000
        body = f"{x:.2f}".rstrip("0").rstrip(".")
        return f"{symbol}{body}M"
    if a >= 1_000:
        x = amount / 1_000
        body = f"{x:.2f}".rstrip("0").rstrip(".")
        return f"{symbol}{body}k"
    body = f"{amount:,.2f}".rstrip("0").rstrip(".")
    return f"{symbol}{body}"
