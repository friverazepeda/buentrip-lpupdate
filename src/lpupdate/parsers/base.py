from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from ..pdf_extract import extract_pdf_text


@dataclass
class ParsedUpdateResult:
    update: dict[str, Any]
    provider_output: dict[str, Any] | None = None


class ParseProvider(Protocol):
    name: str

    def parse(self, raw: dict[str, Any]) -> ParsedUpdateResult:
        ...


@dataclass
class SourceBundle:
    body_text: str
    attachment_text: str
    combined_text: str
    attachment_count: int
    attachment_text_present: bool


class UnknownParseProviderError(ValueError):
    pass


def build_source_bundle(raw: dict[str, Any]) -> SourceBundle:
    attachment_texts: list[str] = []
    for attachment in raw.get('attachments', []) or []:
        storage_path = attachment.get('storage_path')
        mime_type = (attachment.get('mime_type') or '').lower()
        if not storage_path:
            continue
        if mime_type == 'application/pdf' or str(storage_path).lower().endswith('.pdf'):
            try:
                text = extract_pdf_text(storage_path)
            except Exception:
                text = ''
            if text:
                attachment_texts.append(text)

    attachment_text = '\n\n'.join(attachment_texts)
    body_text = raw.get('body_text') or ''
    combined_text = '\n\n'.join(part for part in [body_text, attachment_text] if part)
    return SourceBundle(
        body_text=body_text,
        attachment_text=attachment_text,
        combined_text=combined_text,
        attachment_count=len(raw.get('attachments', []) or []),
        attachment_text_present=bool(attachment_text),
    )


def get_parse_provider(settings) -> ParseProvider:
    provider = (settings.parse_provider or 'rules').strip().lower()
    if provider == 'rules':
        from .rules import RulesParseProvider

        return RulesParseProvider()
    if provider == 'bem':
        from .bem import BemParseProvider

        return BemParseProvider(settings)
    if provider == 'hybrid':
        from .hybrid import HybridParseProvider

        return HybridParseProvider(settings)
    raise UnknownParseProviderError(f'Unknown parse provider: {provider}')
