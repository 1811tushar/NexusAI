import pytest

from app.rag.cleaner import clean_pages, clean_text
from app.rag.errors import IngestionError
from app.rag.loader import PageText, load_document
from tests.helpers import encrypt_pdf, make_docx, make_pdf


def test_txt_and_md():
    d = load_document(b"Hello\nWorld", "TXT")
    assert d.page_count is None and d.pages[0].text == "Hello\nWorld"
    d = load_document(b"# T\n\nbody", "MD")
    assert "# T" in d.pages[0].text


def test_txt_latin1_warns_and_binary_rejected():
    d = load_document("café".encode("latin-1"), "TXT")
    assert "café" in d.pages[0].text and d.warnings
    with pytest.raises(IngestionError, match="binary"):
        load_document(b"abc\x00\x01\x02" * 10, "TXT")


def test_pdf_pages_and_numbers():
    d = load_document(make_pdf(["Revenue fell in the South region.", "Supplier incident note."]), "PDF")
    assert d.page_count == 2 and [p.page for p in d.pages] == [1, 2]
    assert "Revenue fell" in d.pages[0].text and "Supplier" in d.pages[1].text


def test_pdf_encrypted_corrupt_empty_scanned():
    with pytest.raises(IngestionError, match="password"):
        load_document(encrypt_pdf(make_pdf(["secret text here for the page"])), "PDF")
    with pytest.raises(IngestionError, match="corrupt|PDF"):
        load_document(b"%PDF-1.4 garbage garbage", "PDF")
    with pytest.raises(IngestionError, match="not a valid PDF"):
        load_document(b"hello world", "PDF")
    with pytest.raises(IngestionError, match="scanned"):
        load_document(make_pdf(["", ""]), "PDF")
    with pytest.raises(IngestionError, match="empty"):
        load_document(b"", "PDF")


def test_pdf_page_limit():
    with pytest.raises(IngestionError, match="limit"):
        load_document(make_pdf(["page text number one"] * 3), "PDF", max_pages=2)


def test_docx_headings_tables():
    data = make_docx([("Title", "Q2 Report"), ("Heading 1", "Revenue"), ("Normal", "Revenue fell 12 percent.")],
                     table=[["Region", "Change"], ["South", "-20%"]])
    d = load_document(data, "DOCX")
    text = d.pages[0].text
    assert "# Q2 Report" in text and "# Revenue" in text and "South | -20%" in text and d.page_count is None


def test_docx_corrupt():
    with pytest.raises(IngestionError):
        load_document(b"PK\x03\x04 not really a docx", "DOCX")
    with pytest.raises(IngestionError, match="not a valid DOCX"):
        load_document(b"plain", "DOCX")


def test_deadline_stops_pdf():
    with pytest.raises(IngestionError, match="too long"):
        load_document(make_pdf(["some text on the page"] * 3), "PDF", deadline=0.0)


def test_cleaner_dehyphenates_and_strips_headers_footers():
    assert clean_text("exam-\nple  text\u00a0ok\x00") == "example text ok"
    pages = [PageText(i, f"ACME CONFIDENTIAL\nBody of page {i} with enough words in it.\n{i}") for i in range(1, 6)]
    out = clean_pages(pages)
    assert all("ACME CONFIDENTIAL" not in p.text and not p.text.strip().endswith(str(p.page)) for p in out)
    assert "Body of page 3" in out[2].text
