"""
Map the LLM JSON payload to the existing ``normalize_update``-compatible dict
used by sync, Django, and the frontend.
"""

from __future__ import annotations

import re
from typing import Any

from ..parse_updates import infer_period
from ..vehicles import canonicalize_company_name
from ..parsers.base import SourceBundle

_CONF_TO_SCORE = {'high': 0.95, 'medium': 0.8, 'low': 0.6}


def _slug_metric_name(name: str, used: set[str]) -> str:
    base = re.sub(r'[^a-z0-9]+', '_', (name or 'metric').lower()).strip('_')[:80] or 'metric'
    slug = base
    n = 2
    while slug in used:
        slug = f'{base}_{n}'
        n += 1
    used.add(slug)
    return slug


def _coerce_str_list(value: Any, *, limit: int = 24) -> list[str]:
    if not value:
        return []
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value[:limit]:
        s = str(item).strip() if item is not None else ''
        if len(s) >= 3:
            out.append(s)
    return out


def _metrics_and_confidence(key_metrics: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    metrics: dict[str, Any] = {}
    confidence: dict[str, Any] = {}
    if not isinstance(key_metrics, list):
        return metrics, confidence
    used_slugs: set[str] = set()
    for m in key_metrics:
        if not isinstance(m, dict):
            continue
        name = m.get('name')
        if not name:
            continue
        slug = _slug_metric_name(str(name), used_slugs)
        val = m.get('value')
        payload: dict[str, Any] = {}
        if val is not None:
            payload['value'] = val
        unit = m.get('unit')
        if unit:
            payload['unit'] = unit
        period = m.get('period')
        if period:
            payload['period'] = period
        currency = m.get('currency')
        if currency:
            payload['currency'] = currency
        metrics[slug] = payload
        conf_label = (m.get('confidence') or 'low').lower()
        if conf_label not in _CONF_TO_SCORE:
            conf_label = 'low'
        confidence[slug] = {
            'score': _CONF_TO_SCORE[conf_label],
            'origin': 'llm_extraction',
            'confidence_label': conf_label,
            'source_snippet': '',
        }
    return metrics, confidence


def llm_extraction_to_parsed_update(
    raw: dict[str, Any],
    bundle: SourceBundle,
    llm: dict[str, Any],
) -> dict[str, Any]:
    """Build the same top-level shape as :func:`lpupdate.parse_updates.normalize_update`."""
    combined_for_period = '\n\n'.join(
        part for part in (raw.get('body_text') or '', bundle.attachment_text or '') if part
    )
    period = infer_period(raw.get('subject'), combined_for_period)

    rp = llm.get('reportPeriod')
    if isinstance(rp, str) and rp.strip():
        period['report_period_label'] = rp.strip()
        extra = infer_period(rp, rp)
        for key in ('report_quarter', 'report_year', 'report_month'):
            if extra.get(key) is not None:
                period[key] = extra[key]

    cn = llm.get('companyName')
    company_resolved = None
    if isinstance(cn, str) and cn.strip():
        company_resolved = canonicalize_company_name(cn.strip())
    if not company_resolved:
        company_resolved = canonicalize_company_name(raw.get('company_name_hint'))

    metrics, confidence = _metrics_and_confidence(llm.get('keyMetrics'))

    # extractionNotes and sourceType disagreements are preserved in provider_output (full LLM JSON).

    return {
        'gmail_message_id': raw.get('gmail_message_id'),
        'gmail_thread_id': raw.get('gmail_thread_id'),
        'company_name': company_resolved,
        'subject': raw.get('subject'),
        'from_address': raw.get('from_address'),
        'to_addresses': raw.get('to_addresses', []),
        'received_at': raw.get('received_at'),
        **period,
        'summary': (llm.get('summary') or '').strip() if isinstance(llm.get('summary'), str) else '',
        'metrics_json': metrics,
        'highlights_json': _coerce_str_list(llm.get('highlights')),
        'asks_json': _coerce_str_list(llm.get('asks')),
        'risks_json': _coerce_str_list(llm.get('risks')),
        'people_json': [],
        'confidence_json': confidence,
        'source_path': raw.get('source_path'),
        'parser_version': 'llm-v1',
    }
