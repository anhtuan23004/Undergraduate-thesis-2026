"""PDF text extraction helpers for evaluation evidence builders."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from eval.paths import ROOT


def extract_pdf_text(file_path: Any, max_chars: int = 20000) -> str:
    """Extract bounded text from a local PDF path, returning an empty string if missing."""
    if not file_path:
        return ""
    path = Path(str(file_path))
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        return ""

    import fitz

    chunks: list[str] = []
    with fitz.open(path) as document:
        for page in document:
            chunks.append(page.get_text("text"))
            if sum(len(chunk) for chunk in chunks) >= max_chars:
                break
    text = "\n".join(chunks).strip()
    return text[:max_chars]
