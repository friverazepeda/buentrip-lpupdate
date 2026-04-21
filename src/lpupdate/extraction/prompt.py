"""
Prompt and schema contract for LLM extraction.

The model must return a single JSON object (no markdown) matching
:const:`EXTRACTION_RESPONSE_SCHEMA_DESCRIPTION` and the user-facing rules below.
"""

from __future__ import annotations

# Verbatim core rules from product spec (embedded in the system message).
CORE_EXTRACTION_RULES = """You are extracting investor update data for a venture portfolio reporting system.

Return only valid JSON matching the provided schema.

Rules:
- Do not include markdown.
- Do not include explanatory prose.
- Do not invent facts not present in the source text.
- Clean out email/header/transcript artifacts such as "Subject:", forwarding lines, signatures, timestamps, and speaker labels unless needed for meaning.
- summary must be a clean paragraph.
- highlights, asks, and risks must be arrays of concise strings.
- keyMetrics must include only metrics explicitly present or directly inferable from clearly labeled values in the source.
- If a startup is pre-revenue or the source does not provide metrics, return an empty keyMetrics array.
- Prefer omission over guessing."""

# JSON shape the model must produce (field names are fixed for downstream mapping).
EXTRACTION_RESPONSE_SCHEMA_DESCRIPTION = """
{
  "companyName": "string or null",
  "reportPeriod": "string or null",
  "sourceType": "gmail|pdf|fathom|mixed",
  "summary": "string",
  "highlights": ["string"],
  "asks": ["string"],
  "risks": ["string"],
  "keyMetrics": [
    {
      "name": "string",
      "value": "number|string",
      "unit": "string or null",
      "period": "string or null",
      "currency": "string or null",
      "confidence": "high|medium|low"
    }
  ],
  "extractionNotes": ["string"]
}
"""


def system_message() -> str:
    return (
        CORE_EXTRACTION_RULES
        + "\n\nThe JSON object must use exactly these keys and types:\n"
        + EXTRACTION_RESPONSE_SCHEMA_DESCRIPTION
    )


def user_message(envelope: str) -> str:
    """Wrap labeled source text from :func:`lpupdate.extraction.adapter.build_extraction_envelope`."""
    return (
        "Extract structured data from the following source. "
        "Respond with one JSON object only.\n\n"
        + envelope
    )
