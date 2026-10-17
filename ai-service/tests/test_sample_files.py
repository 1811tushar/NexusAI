"""The committed sample files in tests/data go through the real loader / pipeline (AI-RG-01, AI-RG-03)."""
from pathlib import Path

import pytest

from app.core.config import Settings
from app.rag.chunker import chunk_document
from app.rag.errors import IngestionError
from app.rag.loader import load_document

DATA = Path(__file__).parent / "data"


def _read(name: str) -> bytes:
    return (DATA / name).read_bytes()


def test_txt_md_samples_load():
    assert "South region" in load_document(_read("sample.txt"), "TXT").pages[0].text
    assert "# Pricing policy" in load_document(_read("sample.md"), "MD").pages[0].text


def test_pdf_sample_has_two_numbered_pages():
    d = load_document(_read("sample.pdf"), "PDF")
    assert d.page_count == 2 and [p.page for p in d.pages] == [1, 2]
    chunks = chunk_document(d.pages)
    assert {c.page for c in chunks} == {1, 2}          # a chunk never spans two pages


def test_docx_sample_has_headings_and_table():
    d = load_document(_read("sample.docx"), "DOCX")
    text = "\n".join(p.text for p in d.pages)
    assert "Budget" in text and "North" in text and "12000" in text


@pytest.mark.parametrize("name,fragment", [
    ("sample_encrypted.pdf", "password"),
    ("sample_scanned.pdf", "scanned"),
    ("sample_corrupt.pdf", "corrupt"),
])
def test_bad_pdf_samples_fail_with_readable_reason(name, fragment):
    with pytest.raises(IngestionError) as exc:
        load_document(_read(name), "PDF")
    assert fragment in str(exc.value).lower()


def test_settings_defaults_are_sane():
    s = Settings(_env_file=None, internal_api_key="x" * 20, ai_db_rw_password="a", ai_db_ro_password="b")
    assert s.chunk_overlap_tokens < s.chunk_tokens and s.chunking_mode == "semantic"
