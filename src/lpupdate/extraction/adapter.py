"""
Normalize raw Gmail / Fathom records plus :class:`~lpupdate.parsers.base.SourceBundle`
into a single labeled block for the LLM user message.
"""

from __future__ import annotations

from typing import Any

from ..parsers.base import SourceBundle

# Truncate very large inputs to stay within model context (characters, approximate).
_MAX_COMBINED_CHARS = 120_000


def infer_source_type_label(raw: dict[str, Any], bundle: SourceBundle) -> str:
    """
    Suggest sourceType for the model (gmail|pdf|fathom|mixed).
    Final value is chosen by the model per schema; this is a hint in the envelope.
    """
    st = (raw.get('source_type') or '').strip().lower()
    if st == 'fathom_meeting':
        return 'fathom'
    has_body = bool((raw.get('body_text') or '').strip())
    has_pdf = bundle.attachment_text_present
    if has_body and has_pdf:
        return 'mixed'
    if has_pdf:
        return 'pdf'
    return 'gmail'


def build_extraction_envelope(raw: dict[str, Any], bundle: SourceBundle) -> str:
    """
    Build consistent, labeled text so email body, PDF extraction, and Fathom
    blocks are identifiable without separate code paths in the LLM module.
    """
    lines: list[str] = []
    subj = raw.get('subject') or ''
    if subj:
        lines.append(f"Subject: {subj}")
    src_hint = infer_source_type_label(raw, bundle)
    lines.append(f"Source hint: {src_hint}")
    lines.append(f"Has PDF attachment text: {'yes' if bundle.attachment_text_present else 'no'}")
    if raw.get('from_address'):
        lines.append(f"From: {raw.get('from_address')}")
    if raw.get('company_name_hint'):
        lines.append(f"Company hint (from ingestion): {raw.get('company_name_hint')}")
    lines.append('')
    lines.append('--- EMAIL / BODY TEXT ---')
    lines.append((raw.get('body_text') or '').strip() or '(empty)')
    lines.append('')
    lines.append('--- PDF / ATTACHMENT TEXT ---')
    lines.append((bundle.attachment_text or '').strip() or '(none)')
    text = '\n'.join(lines).strip()
    if len(text) > _MAX_COMBINED_CHARS:
        text = text[:_MAX_COMBINED_CHARS] + '\n\n[...truncated for model context...]'
    return text
