"""
Parse provider that extracts startup updates via OpenAI (Chat Completions).

Enable with ``LPUPDATE_PARSE_PROVIDER=llm`` and set ``OPENAI_API_KEY``.
The rules/BEM/hybrid providers are unchanged; this is an additive path.
"""

from __future__ import annotations

from typing import Any

from ..extraction.map_to_update import llm_extraction_to_parsed_update
from ..extraction.openai_extract import extract_from_raw_and_bundle
from .base import ParsedUpdateResult, build_source_bundle


class LlmParseProvider:
    name = 'llm'

    def __init__(self, settings: Any) -> None:
        self.settings = settings

    def parse(self, raw: dict[str, Any]) -> ParsedUpdateResult:
        api_key = getattr(self.settings, 'openai_api_key', None)
        if not api_key:
            raise ValueError(
                'OPENAI_API_KEY is not set. Export it, or use parse_provider=rules|bem|hybrid.'
            )
        model = getattr(self.settings, 'openai_model', None)

        bundle = build_source_bundle(raw)
        enriched = dict(raw)
        enriched['attachment_text'] = bundle.attachment_text

        llm_json = extract_from_raw_and_bundle(
            enriched,
            bundle,
            api_key=api_key,
            model=model,
        )
        update = llm_extraction_to_parsed_update(enriched, bundle, llm_json)
        update['parser_provider'] = self.name
        return ParsedUpdateResult(update=update, provider_output=llm_json)
