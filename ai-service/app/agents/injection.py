"""Prompt-injection hardening and input rules (AI-SF-01, ADD-GR-01).
* Everything from outside (documents, web pages, memories, tool outputs) is wrapped in explicit <untrusted_data> delimiters; the closing tag inside the
  content is neutralised so it cannot break out. System prompts state that such text is DATA.
* `classify_input` = deterministic first stage of the input guardrail (the LLM classifier only sees ambiguous cases)."""
from __future__ import annotations

import re
from dataclasses import dataclass

OPEN_TAG, CLOSE_TAG = "<untrusted_data", "</untrusted_data>"


def wrap_untrusted(text: str, source: str) -> str:
    safe = str(text).replace("</untrusted_data", "</ untrusted_data").replace("<untrusted_data", "< untrusted_data")
    return f'{OPEN_TAG} source="{source[:120]}">\n{safe}\n{CLOSE_TAG}'


_INJECTION_IN_DATA = re.compile(
    r"(ignore|disregard|forget)\s+(all\s+|any\s+|the\s+)?(previous|prior|above|earlier)\s+(instructions?|rules?|prompts?)"
    r"|approve\s+(all|every)\s+(pending\s+)?(actions?|requests?)"
    r"|reveal\s+(your\s+)?(system\s+)?prompt|you\s+are\s+now\s+(in\s+)?(developer|dan|unrestricted)"
    r"|(mark|label|set|treat)\s+(every|all|the)?\s*(action|recommendation)s?\s+as\s+low[- ]risk"
    r"|run\s+(this\s+)?sql\s*:?\s*(delete|drop|update|insert)", re.I)


def looks_like_injection(text: str) -> bool:
    """Used on retrieved/web content: flagged (never followed). Detection is a signal, the delimiters + no-write-tools are the defence."""
    return bool(_INJECTION_IN_DATA.search(text or ""))


_BLOCK_RULES: list[tuple[str, str, re.Pattern[str]]] = [
    ("PROMPT_INJECTION", "Request tries to override the assistant's instructions.",
     re.compile(r"(ignore|disregard|forget|override)\s+(all\s+|any\s+|the\s+|your\s+)?(previous|prior|above|earlier|safety|system)?\s*"
                r"(instructions?|rules?|guardrails?|prompts?)|reveal\s+(your\s+|the\s+)?(system\s+|hidden\s+)?prompt|show\s+(me\s+)?your\s+(system\s+)?prompt"
                r"|you\s+are\s+now\s+(in\s+)?(developer|dan|unrestricted)|developer\s+mode|jailbreak", re.I)),
    ("UNSAFE_REQUEST", "Request asks the assistant to change data or run write SQL.",
     re.compile(r"\b(delete\s+from|drop\s+(table|database|schema)|truncate\s+table|update\s+\w+\s+set|insert\s+into|alter\s+table|grant\s+all)\b", re.I)),
    ("UNSAFE_REQUEST", "Request tries to bypass or fake the approval process.",
     re.compile(r"\b(approve|authori[sz]e)\s+(all|every|everything)\b|\b(skip|bypass|disable|turn\s+off)\s+(the\s+)?(approval|verification|guardrails?|human\s+review)\b"
                r"|\b(label|mark|set|treat|classify)\b.{0,60}\blow[- ]risk\b|\bwithout\s+(asking\s+for\s+)?(approval|an\s+approver)\b", re.I)),
    ("UNSAFE_REQUEST", "Request asks for private account data or credentials.",
     re.compile(r"\b(select\s+\*\s+from\s+(users|refresh_tokens|approvals)|dump\s+(the\s+)?(users?|passwords?|tokens?)|(show|list|give|print)\b.{0,30}\b(passwords?|api\s*keys?|secrets?|tokens?)\b)", re.I)),
    ("UNSAFE_REQUEST", "Request asks to extract personal data.",
     re.compile(r"\b(list|show|give|extract|dump|print)\b.{0,50}\b(e-?mail\s+addresses|phone\s+numbers|aadhaar|ssn|social\s+security|card\s+numbers?|credit\s+card|\bpan\s+numbers?)\b", re.I)),
]

_BUSINESS = re.compile(
    r"\b(revenue|sales?|region|regions|product|products|customer|customers|churn|marketing|campaign|spend|budget|price|pricing|margin|profit|cost|costs|"
    r"quarter|q[1-4]|month|year|decline|decrease|increase|growth|grew|fell|drop|supplier|competitor|policy|approval|approver|report|document|forecast|"
    r"category|home|electronics|apparel|north|south|east|west|inventory|stock|units|orders?|kpi|trend|why|compare|summar\w+|investigate|management)\b", re.I)
_SOFT = re.compile(r"\b(ignore|pretend|instruction|instructions|prompt|password|credentials|secret|api\s*key|hack|bypass|confidential|salary|override|exploit)\b", re.I)


@dataclass(frozen=True)
class InputVerdict:
    verdict: str                 # BLOCK | ALLOW | AMBIGUOUS
    category: str | None = None
    detail: str = ""


def classify_input(question: str) -> InputVerdict:
    for category, detail, pattern in _BLOCK_RULES:
        if pattern.search(question):
            return InputVerdict("BLOCK", category, detail)
    if _SOFT.search(question) or not _BUSINESS.search(question):
        return InputVerdict("AMBIGUOUS")
    return InputVerdict("ALLOW")
