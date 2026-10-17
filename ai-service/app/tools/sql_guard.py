"""SQL guard (AI-TL-02, SEC-03): sqlglot AST validation. Defence in depth: this runs BEFORE the read-only role / read-only transaction / timeout.
Rules: exactly ONE statement, root is a plain SELECT (no UNION), only the five business tables (CTE names allowed), no schema other than `public`,
no write/DDL/command nodes anywhere (so data-modifying CTEs are rejected), no SELECT INTO / FOR UPDATE, no parameters, only allow-listed unknown functions
(pg_sleep, pg_read_file, dblink, set_config ... are rejected), forced LIMIT. The EXECUTED SQL is re-rendered from the AST, so comment tricks never reach the DB."""
from __future__ import annotations

from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError, TokenError

ALLOWED_TABLES = frozenset({"regions", "products", "sales", "marketing_spend", "customer_metrics"})
MAX_SQL_CHARS = 4000

# Functions sqlglot does not model natively (parsed as Anonymous) that we explicitly allow. Everything else Anonymous is rejected.
ALLOWED_ANON_FUNCS = frozenset({
    "greatest", "least", "stddev", "stddev_pop", "stddev_samp", "variance", "var_pop", "var_samp", "corr", "regr_slope",
    "regr_intercept", "width_bucket", "trunc", "sign", "mod", "power", "sqrt", "ln", "log", "exp", "date_part", "age",
    "initcap", "split_part", "to_char", "date_trunc", "extract", "round", "ceil", "ceiling", "floor", "abs", "coalesce",
    "nullif", "concat", "length", "lower", "upper", "substr", "substring", "replace", "trim", "cast", "percentile_cont",
    "percentile_disc", "mode", "median", "row_number", "rank", "dense_rank", "lag", "lead", "first_value", "last_value",
    "ntile", "cume_dist", "percent_rank", "sum", "avg", "count", "min", "max",
})

_FORBIDDEN_NODE_NAMES = (
    "Insert", "Update", "Delete", "Drop", "Create", "Merge", "Copy", "Command", "Set", "Use", "Show", "Describe", "TruncateTable",
    "Grant", "Transaction", "Commit", "Rollback", "Declare", "Kill", "Alter", "Analyze", "Cache", "Uncache", "LoadData", "Comment",
    "Refresh", "Attach", "Detach", "Pragma", "Execute", "Into", "Lock", "CurrentUser", "CurrentSchema", "CurrentSchemas",
    "SessionUser", "Placeholder", "Parameter", "SessionParameter", "SetOperation", "Union", "Intersect", "Except", "Values",
    "Unnest", "Lateral", "Pivot", "Export", "Install", "Summarize", "Vacuum",
    # typed functions that reveal server/session internals or have side effects (everything unknown is already rejected as Anonymous)
    "CurrentVersion", "CurrentDatabase", "CurrentCatalog", "CurrentRole", "CurrentSchemas", "SessionUser", "User", "Uuid", "Rand", "Format",
)
_FORBIDDEN_NODES = tuple(getattr(exp, n) for n in _FORBIDDEN_NODE_NAMES if hasattr(exp, n))


@dataclass
class GuardResult:
    ok: bool
    sql: str | None = None
    reason: str | None = None
    tables: list[str] = field(default_factory=list)


def _reject(reason: str) -> GuardResult:
    return GuardResult(False, None, reason)


def _limit_value(root: exp.Select) -> int | None:
    lim = root.args.get("limit")
    node = None
    if isinstance(lim, exp.Limit):
        node = lim.expression
    elif isinstance(lim, exp.Fetch):
        node = lim.args.get("count")
    if isinstance(node, exp.Literal) and not node.is_string:
        try:
            return int(node.this)
        except ValueError:
            return None
    return None


def validate_sql(sql: str, *, row_limit: int = 200) -> GuardResult:
    """Return GuardResult(ok, sql=<safe re-rendered SQL with forced LIMIT>) or (ok=False, reason=<readable>)."""
    if not isinstance(sql, str) or not sql.strip():
        return _reject("The query is empty.")
    if len(sql) > MAX_SQL_CHARS:
        return _reject(f"The query is too long (max {MAX_SQL_CHARS} characters).")
    try:
        statements = sqlglot.parse(sql, dialect="postgres")
    except (ParseError, TokenError) as exc:
        return _reject(f"SQL could not be parsed: {str(exc).splitlines()[0][:160]}")
    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        return _reject("Exactly one SELECT statement is allowed (no multiple statements).")
    root = statements[0]
    if not isinstance(root, exp.Select):
        return _reject(f"Only a single SELECT is allowed (got {type(root).__name__.upper()}). UNION / INTERSECT / EXCEPT are not allowed.")

    for node in root.walk():
        if isinstance(node, _FORBIDDEN_NODES):
            return _reject(f"{type(node).__name__.upper()} is not allowed in a read-only analysis query.")

    for node in root.walk():
        node.comments = None                       # comments never reach the database (the SQL is re-rendered from the AST)

    cte_names = {c.alias_or_name.lower() for c in root.find_all(exp.CTE)}
    tables: list[str] = []
    for t in root.find_all(exp.Table):
        if not isinstance(t.this, exp.Identifier):
            return _reject("Table-valued functions are not allowed.")
        name = t.name.lower()
        if t.args.get("catalog"):
            return _reject("Cross-database references are not allowed.")
        db = (t.args["db"].name.lower() if t.args.get("db") else "")
        if db and db != "public":
            return _reject(f"Schema '{db}' is not allowed. Use only: {', '.join(sorted(ALLOWED_TABLES))}.")
        if not db and name in cte_names:
            continue
        if name not in ALLOWED_TABLES:
            return _reject(f"Table '{name}' is not allowed. Use only: {', '.join(sorted(ALLOWED_TABLES))}.")
        tables.append(name)

    for fn in root.find_all(exp.Anonymous):
        fname = (fn.name or "").lower()
        if fname not in ALLOWED_ANON_FUNCS:
            return _reject(f"Function '{fname}' is not allowed.")

    lim = _limit_value(root)
    capped = row_limit if lim is None else min(lim, row_limit)
    root.set("limit", exp.Limit(expression=exp.Literal.number(capped)))
    return GuardResult(True, root.sql(dialect="postgres"), None, sorted(set(tables)))
