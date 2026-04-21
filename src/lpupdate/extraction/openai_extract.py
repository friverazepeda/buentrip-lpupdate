"""
OpenAI Chat Completions API: structured JSON extraction for startup updates.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from .adapter import build_extraction_envelope
from .prompt import system_message, user_message

logger = logging.getLogger(__name__)


def _parse_json_content(content: str) -> dict[str, Any]:
    text = (content or '').strip()
    if not text:
        raise ValueError('empty model response')
    # Rare: model wraps in ```json ... ```
    if text.startswith('```'):
        lines = text.split('\n')
        if lines[-1].strip() == '```':
            lines = lines[1:-1]
        elif lines[0].startswith('```'):
            lines = lines[1:]
        text = '\n'.join(lines)
    return json.loads(text)


def extract_with_openai(
    *,
    envelope: str,
    api_key: str,
    model: str | None = None,
) -> dict[str, Any]:
    """
    Call OpenAI and return the parsed JSON object (companyName, keyMetrics, ...).

    Uses the Chat Completions API with ``response_format`` set to JSON object.
    """
    try:
        from openai import OpenAI
    except ModuleNotFoundError as e:
        raise RuntimeError(
            'The openai package is required for LLM extraction. '
            'Install with: pip install openai'
        ) from e

    client = OpenAI(api_key=api_key)
    model_name = (model or 'gpt-4o-mini').strip()

    completion = client.chat.completions.create(
        model=model_name,
        temperature=0.2,
        response_format={'type': 'json_object'},
        messages=[
            {'role': 'system', 'content': system_message()},
            {'role': 'user', 'content': user_message(envelope)},
        ],
    )
    choice = completion.choices[0]
    content = choice.message.content or ''
    try:
        return _parse_json_content(content)
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning('LLM returned non-JSON or empty content: %s', content[:500])
        raise ValueError(f'invalid JSON from model: {e}') from e


def extract_from_raw_and_bundle(
    raw: dict[str, Any],
    bundle: Any,
    *,
    api_key: str,
    model: str | None = None,
) -> dict[str, Any]:
    """Convenience: build envelope from ``raw`` + bundle and run extraction."""
    from ..parsers.base import SourceBundle

    if not isinstance(bundle, SourceBundle):
        raise TypeError('bundle must be a SourceBundle')
    env = build_extraction_envelope(raw, bundle)
    return extract_with_openai(envelope=env, api_key=api_key, model=model)
