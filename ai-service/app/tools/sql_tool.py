"""sql_query tool (AI-TL-02): guard -> read-only pool -> READ ONLY transaction -> statement timeout. Runs ONLY on the ai_readonly pool.
A rejection / DB error is returned to the agent as a readable ToolError so it can correct its query (bounded by the failure policy)."""
from __future__ import annotations

from typing import TYPE_CHECKING

import psycopg
from pydantic import BaseModel, Field

from app.agents.injection import wrap_untrusted
from app.tools.evidence_utils import jsonable, table_evidence, text_table
from app.tools.registry import ToolError, ToolResult
from app.tools.sql_guard import validate_sql

if TYPE_CHECKING:
    from app.agents.context import RunContext


class SqlArgs(BaseModel):
    sql: str = Field(min_length=1, max_length=4000, description="one PostgreSQL SELECT over regions, products, sales, marketing_spend, customer_metrics")


def run_sql(ctx: RunContext, args: SqlArgs) -> ToolResult:
    fault = ctx.faults.take("sql_query") if ctx.faults else None
    if fault == "timeout":
        raise ToolError("The query exceeded the time limit.", transient=True)
    if fault == "error":
        raise ToolError("The database reported an internal error.")
    guard = validate_sql(args.sql, row_limit=ctx.settings.sql_row_limit)
    if not guard.ok:
        ctx.guardrail("TOOL", "BLOCKED", "UNSAFE_REQUEST", f"SQL rejected: {guard.reason}")
        raise ToolError(f"Query rejected by the SQL guard: {guard.reason}")
    assert guard.sql is not None
    if fault == "empty":
        columns, rows = ["result"], []
    else:
        try:
            with ctx.ro_pool.connection() as conn, conn.transaction():
                conn.execute("SET TRANSACTION READ ONLY")
                cur = conn.execute(guard.sql)
                columns = [d.name for d in cur.description or []]
                rows = [[jsonable(r[c]) for c in columns] for r in cur.fetchall()]
        except psycopg.errors.QueryCanceled as exc:
            raise ToolError(f"The query exceeded the {ctx.settings.sql_timeout_ms} ms time limit; make it cheaper (filter months, aggregate).",
                            transient=False) from exc
        except psycopg.errors.OperationalError as exc:
            raise ToolError("The database is temporarily unavailable.", transient=True) from exc
        except psycopg.Error as exc:
            msg = (getattr(getattr(exc, "diag", None), "message_primary", None) or "database error")[:200]
            raise ToolError(f"The database rejected the query: {msg}") from exc
    title = "SQL result: " + (", ".join(guard.tables) or "query")
    ev = table_evidence("SQL", title, columns, rows, source={"sql": guard.sql, "table": ",".join(guard.tables) or None})
    obs = wrap_untrusted(text_table(columns, rows, 25) if rows else "(no rows returned)", "sql_query result")
    return ToolResult(summary=f"{len(rows)} row(s), columns: {', '.join(columns)[:120]}", observation=obs, evidence=[ev] if rows else [])
