Tiny sample documents used by `tests/test_sample_files.py` (all synthetic, no real data):

| File | What it is |
|---|---|
| `sample.txt`, `sample.md` | plain text and Markdown with a heading |
| `sample.pdf` | 2-page text PDF (page numbers must survive) |
| `sample_encrypted.pdf` | the same PDF, password-protected (password `secret`) -> must be rejected with a clear message |
| `sample_scanned.pdf` | 2 pages with no text layer (like a scan) -> rejected, OCR is not enabled |
| `sample_corrupt.pdf` | not a real PDF -> rejected |
| `sample.docx` | headings + a table |

Other tests still build ad-hoc documents in code with `tests/helpers.py`. To regenerate these files see the snippet in `REPORT.md`.
