"""Programmatic citation validation (ADD-GR-03). Runs AFTER the reporter. For every sentence/bullet of the LLM-written report body:
  1. every cited label [E#] must exist (unknown ones are removed);
  2. numbers in the sentence must appear in the cited evidence (SQL/STATS tables, chart series, snippets) within rounding; uncited sentences are checked
     against ALL evidence; numbers the LLM computed itself fail;
  3. quoted text (>= 4 words) must be a substring / near-match of the cited evidence;
  4. a bullet under 'Findings' with no valid citation is not allowed to stand as a finding.
A failing sentence is REMOVED from the findings and returned in `moved` so the reporter lists it under 'Unverified'. Pure code, no LLM."""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Any

LABEL_RE = re.compile(r"\[(E\d+)\]")
_NUM = re.compile(r"(?<![\w.])([$₹€£]\s?)?(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?\s?(%|k\b|m\b|b\b|million\b|billion\b|thousand\b)?", re.I)
_QUOTE = re.compile(r"[\"“]([^\"”]{12,})[\"”]")
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\[])")
_MULT = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6, "b": 1e9, "billion": 1e9}


def split_sentences(text: str) -> list[str]:
    """Sentence split that keeps a trailing marker ('... 2026. [E1]') with the sentence it cites."""
    out: list[str] = []
    for part in _SENT_SPLIT.split(text):
        if out and not LABEL_RE.sub("", part).strip() and LABEL_RE.search(part):
            out[-1] = out[-1] + " " + part.strip()
        else:
            out.append(part)
    return out


@dataclass
class CitationResult:
    markdown: str
    moved: list[tuple[str, str]] = field(default_factory=list)       # (sentence without markers, reason)
    issues: dict[str, int] = field(default_factory=dict)
    cited_units: int = 0
    valid_units: int = 0

    @property
    def validity(self) -> float | None:
        return round(self.valid_units / self.cited_units, 3) if self.cited_units else None

    def detail(self) -> str:
        parts = ", ".join(f"{n} {k}" for k, n in sorted(self.issues.items()))
        return f"{len(self.moved)} statement(s) moved to Unverified: {parts}." if self.moved else ""


def numbers_in(text: str, *, only_significant: bool) -> list[tuple[float, int]]:
    """(value, decimals) pairs. 'Significant' = has %/currency/decimals/grouping or >= 100 and not a plain year."""
    out: list[tuple[float, int]] = []
    for m in _NUM.finditer(text):
        cur, whole, frac, suf = m.group(1), m.group(2), m.group(3), (m.group(4) or "").lower()
        digits = whole.replace(",", "") + (frac or "")
        try:
            v = float(digits)
        except ValueError:
            continue
        dp = len(frac) - 1 if frac else 0
        mult = _MULT.get(suf, 1.0)
        significant = bool(cur or frac or "," in whole or suf or v >= 100)
        if suf == "" and not cur and not frac and "," not in whole and 1900 <= v <= 2100:
            significant = False
        if only_significant and not significant:
            continue
        out.append((v * mult, dp if mult == 1.0 else max(dp, 0)))
        if mult != 1.0:
            out[-1] = (v * mult, -int(len(str(int(mult))) - 1) + dp)   # rounding unit = 10^-dp * mult
    return out


def evidence_text(ev: dict[str, Any]) -> str:
    parts = [str(ev.get("title", "")), str(ev.get("snippet", ""))]
    data = ev.get("data") or {}
    for row in data.get("rows", []):
        parts.append(" ".join("" if c is None else str(c) for c in row))
    for s in (ev.get("chart") or {}).get("series", []):
        parts.append(" ".join(str(v) for v in s.get("values", [])))
    return "\n".join(parts)


def evidence_numbers(evs: list[dict[str, Any]]) -> list[float]:
    nums: list[float] = []
    for ev in evs:
        text = evidence_text(ev)
        for m in re.finditer(r"-?\d[\d,]*\.?\d*", text):
            try:
                v = abs(float(m.group(0).replace(",", "")))
            except ValueError:
                continue
            nums.extend([v, v * 100, v / 100, v / 1000, v / 1e6])
    return nums


def number_supported(v: float, dp: int, nums: list[float]) -> bool:
    v = abs(v)
    tol = max(0.5 * (10 ** -dp) if dp >= 0 else 0.5 * (10 ** -dp), 0.005 * v)
    return any(abs(e - v) <= tol for e in nums)


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s%.$]", " ", t.lower())).strip()


def quote_supported(quote: str, texts: list[str]) -> bool:
    q = _norm(quote)
    for t in texts:
        n = _norm(t)
        if q in n:
            return True
        step, w = 12, len(q) + 24
        for i in range(0, max(1, len(n) - len(q) + 1), step):
            if difflib.SequenceMatcher(None, q, n[i:i + w]).ratio() >= 0.85:
                return True
    return False


def check_report(markdown: str, labels: dict[str, dict[str, Any]]) -> CitationResult:
    res = CitationResult(markdown="")
    all_nums = evidence_numbers(list(labels.values()))
    out: list[str] = []
    section = ""

    def flag(kind: str) -> None:
        res.issues[kind] = res.issues.get(kind, 0) + 1

    for raw in markdown.split("\n"):
        line = raw.rstrip()
        if line.lstrip().startswith("#"):
            section = line.lstrip("# ").strip().lower()
            out.append(line)
            continue
        if not line.strip():
            out.append(line)
            continue
        m = re.match(r"^(\s*(?:[-*]|\d+[.)])\s+)(.*)$", line)
        prefix, body = (m.group(1), m.group(2)) if m else ("", line)
        units = [body] if m else split_sentences(body)
        kept: list[str] = []
        for unit in units:
            found = LABEL_RE.findall(unit)
            unknown = [x for x in found if x not in labels]
            if unknown:
                flag("unknown evidence key")
            clean = re.sub(r"\s+([.,;:!?])", r"\1", LABEL_RE.sub(lambda mm: mm.group(0) if mm.group(1) in labels else "", unit)).strip()
            valid_labels = [x for x in found if x in labels]
            plain = LABEL_RE.sub("", clean).strip()
            substantive = len(plain.split()) >= 5
            reason = None
            if "finding" in section and substantive and not valid_labels:
                reason = "no citation"
            nums = numbers_in(plain, only_significant=True)
            pool = [labels[x] for x in valid_labels] if valid_labels else list(labels.values())
            pool_nums = evidence_numbers(pool) if valid_labels else all_nums
            if reason is None and any(not number_supported(v, dp, pool_nums) for v, dp in nums):
                reason = "number not found in the cited evidence"
            if reason is None:
                for q in _QUOTE.findall(plain):
                    if len(q.split()) >= 4 and not quote_supported(q, [evidence_text(e) for e in pool]):
                        reason = "quoted text not found in the cited evidence"
                        break
            counted = bool(found) or bool(nums)
            if counted:
                res.cited_units += 1
            if reason:
                flag(reason)
                res.moved.append((plain, reason))
                continue
            if counted:
                res.valid_units += 1
            kept.append(clean)
        if kept:
            out.append(prefix + " ".join(kept))
    res.markdown = "\n".join(out)
    return res


def replace_labels(markdown: str, labels: dict[str, dict[str, Any]]) -> str:
    """[E3] -> [ev:<evidenceKey>] so the stored report links to evidence rows independent of numbering."""
    return LABEL_RE.sub(lambda m: f"[ev:{labels[m.group(1)]['evidenceKey']}]" if m.group(1) in labels else "", markdown)
