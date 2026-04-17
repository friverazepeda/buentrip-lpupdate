from __future__ import annotations

from pathlib import Path

try:
    from pypdf import PdfReader
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    PdfReader = None  # type: ignore[assignment]


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
    return "\n\n".join(pages).strip()
