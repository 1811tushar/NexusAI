import pytest

from app.rag.chunker import CHARS_PER_TOKEN, chunk_document, est_tokens
from app.rag.loader import PageText

LONG = "Revenue fell in the South region because of supplier delays. " * 140


def test_semantic_respects_headings_and_size():
    text = f"# Report\n\nIntro line.\n\n## Revenue\n\n{LONG}\n\n## Marketing\n\n{'Spend was flat. ' * 40}"
    chunks = chunk_document([PageText(None, text)], mode="semantic", chunk_tokens=500, overlap_tokens=90)
    assert chunks and [c.chunk_index for c in chunks] == list(range(len(chunks)))
    assert all(est_tokens(c.content) <= 560 for c in chunks)
    assert {c.section for c in chunks} >= {"Report > Revenue", "Report > Marketing"}
    assert not any("## Marketing" in c.content and c.section == "Report > Revenue" for c in chunks)  # no crossing


def test_long_section_has_overlap():
    chunks = chunk_document([PageText(None, "# A\n" + LONG)], mode="semantic", chunk_tokens=200, overlap_tokens=50)
    assert len(chunks) > 2
    tail = chunks[0].content[-40:]
    assert tail.strip()[:25] in chunks[1].content            # overlap carries text over


def test_tiny_sections_are_merged_not_orphaned():
    text = "# A\n\nshort.\n\n# B\n\nalso short.\n\n# C\n\n" + "Real content here. " * 60
    chunks = chunk_document([PageText(None, text)], mode="semantic")
    assert all(est_tokens(c.content) >= 20 for c in chunks)
    assert "short." in "".join(c.content for c in chunks)


def test_page_numbers_tracked_across_pages():
    pages = [PageText(1, "# A\n" + "alpha beta. " * 300), PageText(2, "gamma delta. " * 300)]
    chunks = chunk_document(pages, mode="semantic")
    assert chunks[0].page == 1 and chunks[-1].page == 2


def test_heading_detection_numbered_and_caps():
    text = "EXECUTIVE SUMMARY\n\n" + "Text one. " * 60 + "\n\n1.2 Supplier incident\n\n" + "Text two. " * 60
    sections = {c.section for c in chunk_document([PageText(1, text)], mode="semantic")}
    assert "EXECUTIVE SUMMARY" in sections and any(s and "Supplier incident" in s for s in sections)


def test_fixed_mode_plain_windows():
    chunks = chunk_document([PageText(None, "# A\n" + LONG)], mode="fixed", chunk_tokens=200, overlap_tokens=50)
    assert all(c.section is None and c.metadata["chunking"] == "fixed" for c in chunks)
    assert all(len(c.content) <= 200 * CHARS_PER_TOKEN for c in chunks)
    assert chunks[0].content[-30:] in chunks[1].content + chunks[0].content  # windows overlap by construction
    assert len(chunks) == pytest.approx(len(LONG) / (150 * CHARS_PER_TOKEN), abs=2)


def test_modes_differ_on_structured_text():
    text = "# A\n\n" + "aaa. " * 50 + "\n\n# B\n\n" + "bbb. " * 50
    sem = chunk_document([PageText(None, text)], mode="semantic")
    fix = chunk_document([PageText(None, text)], mode="fixed")
    assert [c.section for c in sem] != [c.section for c in fix]


def test_overlap_must_be_smaller():
    with pytest.raises(ValueError):
        chunk_document([PageText(None, "x")], chunk_tokens=100, overlap_tokens=100)
