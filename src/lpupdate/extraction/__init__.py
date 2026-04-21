"""
LLM-based startup update extraction (alongside the rules/BEM parsers).

See :func:`lpupdate.extraction.openai_extract.extract_with_openai` and
:class:`lpupdate.parsers.llm.LlmParseProvider`.
"""

from .adapter import build_extraction_envelope
from .map_to_update import llm_extraction_to_parsed_update
from .openai_extract import extract_with_openai

__all__ = [
    'build_extraction_envelope',
    'extract_with_openai',
    'llm_extraction_to_parsed_update',
]
