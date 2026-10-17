"""Helpers shared by the tools: JSON-safe values, compact text tables, EvidenceDraft builders."""
from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from app.tools.registry import EvidenceDraft

PREVIEW_ROWS = 50


def jsonable(v: Any) -> Any:
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (dt.date, dt.datetime)):
        return v.isoformat()[:10] if isinstance(v, dt.date) and not isinstance(v, dt.datetime) else v.isoformat()
    if isinstance(v, (str, int, float)) or v is None:
        return v
    return str(v)


def fmt(v: Any) -> str:
    if isinstance(v, float):
        return f"{v:,.2f}".rstrip("0").rstrip(".") if abs(v) < 1e15 else str(v)
    return "" if v is None else str(v)


def text_table(columns: list[str], rows: list[list[Any]], max_rows: int = 20) -> str:
    lines = [" | ".join(columns)]
    lines += [" | ".join(fmt(c) for c in r) for r in rows[:max_rows]]
    if len(rows) > max_rows:
        lines.append(f"... ({len(rows) - max_rows} more rows)")
    return "\n".join(lines)


def table_evidence(kind: str, title: str, columns: list[str], rows: list[list[Any]], *, source: dict[str, Any],
                   chart: dict[str, Any] | None = None, total_rows: int | None = None) -> EvidenceDraft:
    total = total_rows if total_rows is not None else len(rows)
    preview = [[jsonable(c) for c in r] for r in rows[:PREVIEW_ROWS]]
    return EvidenceDraft(kind=kind, title=title[:250], snippet=text_table(columns, rows, 12), source=source,
                         data={"columns": columns, "rows": preview, "truncated": total > PREVIEW_ROWS}, chart=chart, score=None)
