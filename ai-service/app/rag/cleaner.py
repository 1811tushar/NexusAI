"""Text cleaning (AI-RG-01): unicode normalisation, de-hyphenation, repeated header/footer removal, whitespace."""
from __future__ import annotations

import re
import unicodedata
from collections import Counter

from app.rag.loader import PageText

_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_HYPHEN_BREAK = re.compile(r"(\w)-\n(\w)")
_PAGE_NO = re.compile(r"^\s*(?:page\s+)?\d{1,3}(?:\s*(?:/|of)\s*\d{1,4})?\s*$", re.I)


def clean_text(text: str) -> str:
    t = unicodedata.normalize("NFKC", text)
    t = t.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    t = _CTRL.sub("", t)
    t = _HYPHEN_BREAK.sub(r"\1\2", t)
    t = "\n".join(re.sub(r"[ \t]+", " ", ln).rstrip() for ln in t.split("\n"))
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def clean_pages(pages: list[PageText]) -> list[PageText]:
    """Clean each page; for multi-page PDFs also drop lines repeated on >= half the pages (headers/footers) and bare page numbers."""
    cleaned = [PageText(p.page, clean_text(p.text)) for p in pages]
    if len(cleaned) >= 4 and all(p.page is not None for p in cleaned):
        counts: Counter[str] = Counter()
        for p in cleaned:
            counts.update({ln.strip() for ln in p.text.split("\n") if 0 < len(ln.strip()) < 80})
        repeated = {ln for ln, c in counts.items() if c >= len(cleaned) / 2 and not ln.startswith("#")}
        for p in cleaned:
            p.text = "\n".join(ln for ln in p.text.split("\n") if ln.strip() not in repeated)
    if any(p.page is not None for p in cleaned):
        for p in cleaned:
            p.text = "\n".join(ln for ln in p.text.split("\n") if not _PAGE_NO.match(ln))
    for p in cleaned:
        p.text = re.sub(r"\n{3,}", "\n\n", p.text).strip()
    return cleaned
