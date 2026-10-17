"""Versioned prompt files (AI-SF-04). All prompts live in agents/prompts/*.md; code never contains prompt text.
File format: first line `<!-- version: X.Y -->`, SYSTEM text, a line `<!-- USER -->`, then the USER template with {{placeholders}}."""
from __future__ import annotations

import re
from functools import cache
from pathlib import Path

PROMPT_DIR = Path(__file__).parent / "prompts"
_VERSION = re.compile(r"^<!--\s*version:\s*([\w.\-]+)\s*-->\s*", re.I)
_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")
SPLIT = "<!-- USER -->"


@cache
def _load(name: str) -> tuple[str, str, str]:
    raw = (PROMPT_DIR / f"{name}.md").read_text(encoding="utf-8")
    m = _VERSION.match(raw)
    version = m.group(1) if m else "0"
    body = raw[m.end():] if m else raw
    system, _, user = body.partition(SPLIT)
    return version, system.strip(), user.strip()


def prompt_version(name: str) -> str:
    return _load(name)[0]


def render(name: str, **variables: object) -> tuple[str, str]:
    _, system, user = _load(name)

    def sub(text: str) -> str:
        def repl(m: re.Match[str]) -> str:
            key = m.group(1)
            if key not in variables:
                raise KeyError(f"prompt '{name}' needs variable '{key}'")
            return str(variables[key])
        return _PLACEHOLDER.sub(repl, text)

    return sub(system), sub(user)


def all_prompt_names() -> list[str]:
    return sorted(p.stem for p in PROMPT_DIR.glob("*.md"))
