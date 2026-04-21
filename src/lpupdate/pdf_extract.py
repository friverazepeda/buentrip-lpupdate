from __future__ import annotations

import re
from pathlib import Path

try:
    from pypdf import PdfReader
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    PdfReader = None  # type: ignore[assignment]


def normalize_pdf_extracted_text(text: str) -> str:
    """
    Repair common pypdf extraction issues: soft hyphen breaks, mid-sentence
    hard wraps, and excessive blank lines (helps section and KPI line parsing).
    """
    if not text:
        return ""
    t = text.replace("\r\n", "\n").replace("\r", "\n")
    # Soft hyphen + newline often continues a word on the next line.
    t = re.sub(r"-\s*\n\s*([a-z])", r"\1", t, flags=re.IGNORECASE)
    # Two lowercase fragments split across a line break are usually one phrase.
    t = re.sub(r"([a-z])\n([a-z])", r"\1 \2", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    t = re.sub(r"[ \t]+", " ", t)
    return t.strip()


def extract_pdf_text(path: str | Path) -> str:
    # Optional dependency: keep ingestion running even when pypdf is missing.
    if PdfReader is None:
        return ""
    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pages.append("")
    return normalize_pdf_extracted_text("\n\n".join(pages))
