from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader


def extract_pdf_text(path: str | Path) -> str:
    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pages.append("")
    return "\n\n".join(pages).strip()
