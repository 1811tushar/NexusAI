"""Chunking (AI-RG-01, ADDENDUM 09). Two modes, switched by CHUNKING_MODE or the `mode` argument:

* semantic (default): heading-aware. Never crosses a heading boundary (tiny sections are merged into the next one)
  and never spans two PDF pages (page-accurate citations; the cost is no overlap across a page break),
  sections longer than the target are split with a recursive splitter with overlap. Metadata: page, section path.
* fixed: plain fixed-size character windows with overlap, ignoring structure. ONLY for the retrieval ablation.

Token counts are estimated (about 4 characters per token) so no tokenizer is needed at ingest time; BGE-small truncates at 512.
"""
from __future__ import annotations

import bisect
import math
import re
from dataclasses import dataclass, field
from typing import Literal

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.rag.loader import PageText

CHARS_PER_TOKEN = 4
Mode = Literal["fixed", "semantic"]

_MD_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_NUM_HEADING = re.compile(r"^(\d+(?:\.\d+){0,3})[.)]?\s+([A-Z][^\n]{2,70})$")


def est_tokens(text: str) -> int:
    return math.ceil(len(text) / CHARS_PER_TOKEN)


@dataclass
class ChunkRecord:
    chunk_index: int
    page: int | None
    section: str | None
    content: str
    metadata: dict = field(default_factory=dict)

    @property
    def embed_text(self) -> str:
        """Text that gets embedded: the section path is prepended for context; `content` (stored, keyword-indexed) stays raw."""
        if self.section and not self.content.lstrip("# ").startswith(self.section.split(" > ")[-1]):
            return f"{self.section}\n{self.content}"
        return self.content


def _heading(line: str, prev_blank: bool) -> tuple[int, str] | None:
    s = line.strip()
    if not s:
        return None
    m = _MD_HEADING.match(s)
    if m:
        return len(m.group(1)), m.group(2)
    if prev_blank and len(s.split()) <= 12:
        m = _NUM_HEADING.match(s)
        if m and not s.endswith((".", ",", ";", ":")):
            return m.group(1).count(".") + 1, s
        letters = [c for c in s if c.isalpha()]
        if 3 <= len(s) <= 70 and len(letters) >= 3 and s.upper() == s and not s.endswith((".", ",")):
            return 1, s
    return None


@dataclass
class _Section:
    path: str | None
    lines: list[tuple[int | None, str]]

    def text(self) -> str:
        return "\n".join(ln for _, ln in self.lines).strip()

    @property
    def page(self) -> int | None:
        return next((pg for pg, ln in self.lines if ln.strip()), None)


def _split_sections(pages: list[PageText]) -> list[_Section]:
    sections: list[_Section] = [_Section(None, [])]
    stack: list[tuple[int, str]] = []
    prev_blank = True
    for p in pages:
        # PDF pages are hard boundaries: a chunk never spans two pages, so the cited page is always the right one
        if p.page is not None and sections[-1].lines:
            sections.append(_Section(sections[-1].path, []))
            prev_blank = True
        for line in p.text.split("\n"):
            h = _heading(line, prev_blank)
            if h:
                level, title = h
                while stack and stack[-1][0] >= level:
                    stack.pop()
                stack.append((level, title))
                sections.append(_Section(" > ".join(t for _, t in stack), []))
            sections[-1].lines.append((p.page, line))
            prev_blank = not line.strip()
    return [s for s in sections if s.text()]


def _page_index(lines: list[tuple[int | None, str]]) -> tuple[list[int], list[int | None]]:
    offsets, pages, pos = [], [], 0
    for page, ln in lines:
        offsets.append(pos)
        pages.append(page)
        pos += len(ln) + 1
    return offsets, pages


def _page_at(offsets: list[int], pages: list[int | None], offset: int) -> int | None:
    i = max(0, bisect.bisect_right(offsets, offset) - 1)
    return pages[i] if pages else None


def _splitter(chunk_tokens: int, overlap_tokens: int) -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_tokens * CHARS_PER_TOKEN,
        chunk_overlap=overlap_tokens * CHARS_PER_TOKEN,
        separators=["\n\n", "\n", ". ", "; ", ", ", " ", ""],
    )


def _pieces_with_pages(text: str, lines: list[tuple[int | None, str]], splitter) -> list[tuple[str, int | None]]:
    offsets, pages = _page_index(lines)
    out, cursor = [], 0
    for piece in splitter.split_text(text):
        idx = text.find(piece, max(0, cursor - len(piece)))
        if idx < 0:
            idx = cursor
        cursor = idx + 1
        out.append((re.sub(r"^[.!?;,]\s+", "", piece).strip(), _page_at(offsets, pages, idx)))
    out = [(t, pg) for t, pg in out if t]
    # a lone heading (or other tiny leading piece) must not become its own chunk: glue it to the next piece
    while len(out) > 1 and est_tokens(out[0][0]) < 30:
        (t0, pg0), (t1, _) = out[0], out[1]
        out[:2] = [(f"{t0}\n{t1}", pg0)]
    return out


def chunk_document(
    pages: list[PageText], *, mode: Mode = "semantic", chunk_tokens: int = 500, overlap_tokens: int = 90
) -> list[ChunkRecord]:
    if overlap_tokens >= chunk_tokens:
        raise ValueError("overlap must be smaller than the chunk size")
    return (_chunk_fixed if mode == "fixed" else _chunk_semantic)(pages, chunk_tokens, overlap_tokens)


def _chunk_semantic(pages: list[PageText], chunk_tokens: int, overlap_tokens: int) -> list[ChunkRecord]:
    sections = _split_sections(pages)
    splitter = _splitter(chunk_tokens, overlap_tokens)
    min_tokens = max(20, chunk_tokens // 6)
    records: list[ChunkRecord] = []

    def emit(path: str | None, lines: list[tuple[int | None, str]]) -> None:
        text = "\n".join(ln for _, ln in lines).strip()
        if not text:
            return
        if est_tokens(text) <= chunk_tokens:
            first_page = next((pg for pg, ln in lines if ln.strip()), None)
            pieces = [(text, first_page)]
        else:
            pieces = _pieces_with_pages(text, lines, splitter)
        for content, page in pieces:
            records.append(ChunkRecord(len(records), page, path, content, {"chunking": "semantic", "tokensEst": est_tokens(content)}))

    carry: _Section | None = None
    for i, sec in enumerate(sections):
        if carry is not None:
            if carry.page == sec.page:   # never merge across pages
                sec = _Section(sec.path or carry.path, carry.lines + [(None, "")] + sec.lines)  # noqa: PLW2901
            else:
                emit(carry.path, carry.lines)
            carry = None
        if est_tokens(sec.text()) < min_tokens and i < len(sections) - 1:
            carry = sec
            continue
        emit(sec.path, sec.lines)
    if carry is not None:
        emit(carry.path, carry.lines)
    return records


def _chunk_fixed(pages: list[PageText], chunk_tokens: int, overlap_tokens: int) -> list[ChunkRecord]:
    lines: list[tuple[int | None, str]] = []
    for p in pages:
        lines.extend((p.page, ln) for ln in p.text.split("\n"))
        lines.append((p.page, ""))
    text = "\n".join(ln for _, ln in lines)
    offsets, pgs = _page_index(lines)
    size, step = chunk_tokens * CHARS_PER_TOKEN, (chunk_tokens - overlap_tokens) * CHARS_PER_TOKEN
    records: list[ChunkRecord] = []
    for start in range(0, len(text), step):
        window = text[start:start + size]
        if window.strip():
            records.append(ChunkRecord(len(records), _page_at(offsets, pgs, start), None, window.strip(),
                                       {"chunking": "fixed", "tokensEst": est_tokens(window)}))
        if start + size >= len(text):
            break
    return records
