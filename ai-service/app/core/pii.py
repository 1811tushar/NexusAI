"""PII redaction (ADD-GR-02): regex + checksum. Never returns or logs the raw value.

Detects: EMAIL, CARD (Luhn), SSN (US pattern), AADHAAR (Verhoeff), PAN (India), PHONE.
Use before: web search queries, Langfuse payloads, logs, memory summaries.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_EMAIL = re.compile(r"(?<![\w.+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}(?![\w-])")
_CARD = re.compile(r"(?<![\d-])(?:\d[ -]?){12,18}\d(?![\d-])")
_SSN = re.compile(r"(?<![\d-])\d{3}-\d{2}-\d{4}(?![\d-])")
_AADHAAR = re.compile(r"(?<![\d-])[2-9]\d{3}[ -]?\d{4}[ -]?\d{4}(?![\d-])")
_PAN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
_PHONE = re.compile(r"(?<![\w.,])(\+?\d[\d\s().-]{8,18}\d)(?![\w])")
_DATE_LIKE = re.compile(r"^\d{4}[-/.]\d{1,2}[-/.]\d{1,2}$|^\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}$")

# Verhoeff tables
_D = [[0,1,2,3,4,5,6,7,8,9],[1,2,3,4,0,6,7,8,9,5],[2,3,4,0,1,7,8,9,5,6],[3,4,0,1,2,8,9,5,6,7],[4,0,1,2,3,9,5,6,7,8],
      [5,9,8,7,6,0,4,3,2,1],[6,5,9,8,7,1,0,4,3,2],[7,6,5,9,8,2,1,0,4,3],[8,7,6,5,9,3,2,1,0,4],[9,8,7,6,5,4,3,2,1,0]]
_P = [[0,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4],[5,8,0,3,7,9,6,1,4,2],[8,9,1,6,0,4,3,5,2,7],[9,4,5,3,1,2,6,8,7,0],
      [4,2,8,6,5,7,3,9,0,1],[2,7,9,3,8,0,6,4,1,5],[7,0,4,6,9,1,3,2,5,8]]


def verhoeff_valid(number: str) -> bool:
    c = 0
    for i, ch in enumerate(reversed(number)):
        c = _D[c][_P[i % 8][int(ch)]]
    return c == 0


def luhn_valid(number: str) -> bool:
    total, alt = 0, False
    for ch in reversed(number):
        d = int(ch)
        if alt:
            d = d * 2 - 9 if d * 2 > 9 else d * 2
        total += d
        alt = not alt
    return total % 10 == 0


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s)


def _ssn_ok(s: str) -> bool:
    a, g, n = s.split("-")
    return a not in ("000", "666") and not a.startswith("9") and g != "00" and n != "0000"


def _phone_ok(s: str) -> bool:
    d = _digits(s)
    if not 10 <= len(d) <= 15 or _DATE_LIKE.match(s.strip()):
        return False
    if s.lstrip().startswith("+") or re.search(r"[\s().-]", s):
        return not re.fullmatch(r"\d{1,3}(?:[.-]\d{3})+", s)  # 1.250.000 style amounts are not phones
    return bool(re.fullmatch(r"[6-9]\d{9}", d))               # bare 10 digits: only Indian mobile pattern


_DETECTORS: list[tuple[str, re.Pattern[str], callable]] = [  # order = priority when spans overlap
    ("EMAIL", _EMAIL, lambda s: True),
    ("CARD", _CARD, lambda s: 13 <= len(_digits(s)) <= 19 and luhn_valid(_digits(s))),
    ("SSN", _SSN, _ssn_ok),
    ("AADHAAR", _AADHAAR, lambda s: len(_digits(s)) == 12 and verhoeff_valid(_digits(s))),
    ("PAN", _PAN, lambda s: True),
    ("PHONE", _PHONE, _phone_ok),
]


@dataclass
class RedactionResult:
    text: str
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return sum(self.counts.values())

    def to_guardrail_detail(self) -> str:
        """Safe for a `guardrail_triggered.detail`: categories and counts only, never values."""
        return "Redacted " + ", ".join(f"{n} {k}" for k, n in sorted(self.counts.items())) if self.counts else ""


def redact(text: str) -> RedactionResult:
    spans: list[tuple[int, int, str]] = []
    for label, pattern, ok in _DETECTORS:
        for m in pattern.finditer(text):
            s, e = m.start(), m.end()
            if any(s < be and e > bs for bs, be, _ in spans):
                continue
            if ok(m.group(0)):
                spans.append((s, e, label))
    if not spans:
        return RedactionResult(text)
    spans.sort()
    out, pos, counts = [], 0, {}
    for s, e, label in spans:
        out.append(text[pos:s])
        out.append(f"[REDACTED_{label}]")
        counts[label] = counts.get(label, 0) + 1
        pos = e
    out.append(text[pos:])
    return RedactionResult("".join(out), counts)


def redact_text(text: str) -> str:
    return redact(text).text


def contains_pii(text: str) -> bool:
    return redact(text).total > 0
