"""Stats tools (AI-TL-03). pandas on FIXED, parameterised queries over the read-only pool (the LLM never supplies SQL here), so numbers are computed by
code, never by LLM arithmetic. Each tool returns a table + chart-ready series.
  stats_compare      period A vs period B per group: values, absolute and percent change
  stats_contribution which groups drove the net change: change and SHARE of the net change in % (negative share = offsetting growth)
  stats_anomaly      z-score flags on the monthly series (|z| >= threshold)
Metrics: revenue, units, cost, gross_profit (sales) | marketing_spend | active_customers (monthly AVERAGE), new_customers, churned_customers."""
from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Literal

import pandas as pd
from pydantic import BaseModel, Field

from app.agents.injection import wrap_untrusted
from app.tools.evidence_utils import table_evidence, text_table
from app.tools.registry import ToolError, ToolResult

if TYPE_CHECKING:
    from app.agents.context import RunContext

Metric = Literal["revenue", "units", "cost", "gross_profit", "marketing_spend", "active_customers", "new_customers", "churned_customers"]
Dimension = Literal["none", "region", "product", "category", "region_category", "channel"]
MONTH = r"^\d{4}-(0[1-9]|1[0-2])$"

METRIC_TABLE = {"revenue": "sales", "units": "sales", "cost": "sales", "gross_profit": "sales", "marketing_spend": "marketing",
                "active_customers": "customers", "new_customers": "customers", "churned_customers": "customers"}
TABLE_DIMS = {"sales": {"none", "region", "product", "category", "region_category"}, "marketing": {"none", "region", "channel"},
              "customers": {"none", "region"}}
_SQL = {
    "sales": "SELECT s.sale_month AS month, r.name AS region, p.name AS product, p.category, s.units, s.revenue, s.cost FROM sales s "
             "JOIN regions r ON r.id = s.region_id JOIN products p ON p.id = s.product_id WHERE s.sale_month >= %s AND s.sale_month < %s",
    "marketing": "SELECT m.month AS month, r.name AS region, m.channel, m.spend AS marketing_spend FROM marketing_spend m "
                 "JOIN regions r ON r.id = m.region_id WHERE m.month >= %s AND m.month < %s",
    "customers": "SELECT c.month AS month, r.name AS region, c.active_customers, c.new_customers, c.churned_customers FROM customer_metrics c "
                 "JOIN regions r ON r.id = c.region_id WHERE c.month >= %s AND c.month < %s",
}


class Period(BaseModel):
    start: str = Field(pattern=MONTH, description="first month, YYYY-MM")
    end: str = Field(pattern=MONTH, description="last month inclusive, YYYY-MM")


class CompareArgs(BaseModel):
    metric: Metric
    dimension: Dimension = "none"
    period_a: Period = Field(description="baseline period")
    period_b: Period = Field(description="comparison period")


class ContributionArgs(CompareArgs):
    dimension: Dimension = "region"


class AnomalyArgs(BaseModel):
    metric: Metric
    dimension: Dimension = "region"
    start: str = Field(pattern=MONTH)
    end: str = Field(pattern=MONTH)
    z_threshold: float = Field(2.0, ge=1.0, le=5.0)


def _bounds(p_start: str, p_end: str) -> tuple[dt.date, dt.date]:
    s = dt.date(int(p_start[:4]), int(p_start[5:7]), 1)
    e_m = dt.date(int(p_end[:4]), int(p_end[5:7]), 1)
    if e_m < s:
        raise ToolError("Period end must not be before period start.")
    if (e_m.year - s.year) * 12 + e_m.month - s.month > 35:
        raise ToolError("Period too long (max 36 months).")
    end_excl = dt.date(e_m.year + (e_m.month == 12), (e_m.month % 12) + 1, 1)
    return s, end_excl


def _frame(ctx: RunContext, metric: str, start: dt.date, end_excl: dt.date, dimension: str) -> pd.DataFrame:
    table = METRIC_TABLE[metric]
    if dimension not in TABLE_DIMS[table]:
        raise ToolError(f"Dimension '{dimension}' is not available for {metric}. Use one of: {', '.join(sorted(TABLE_DIMS[table]))}.")
    if ctx.faults and (mode := ctx.faults.take("stats")):
        raise ToolError("The statistics backend timed out." if mode == "timeout" else "The statistics backend failed.", transient=mode == "timeout")
    with ctx.ro_pool.connection() as conn, conn.transaction():
        conn.execute("SET TRANSACTION READ ONLY")
        rows = conn.execute(_SQL[table], (start, end_excl)).fetchall()
    df = pd.DataFrame(rows)
    if df.empty:
        raise ToolError("No data in that period (the data covers 2025-01 to 2026-09).")
    for col in ("units", "revenue", "cost", "marketing_spend", "active_customers", "new_customers", "churned_customers"):
        if col in df:
            df[col] = df[col].astype(float)
    if metric == "gross_profit":
        df["gross_profit"] = df["revenue"] - df["cost"]
    df["month"] = pd.to_datetime(df["month"]).dt.strftime("%Y-%m")
    if dimension == "none":
        df["group"] = "TOTAL"
    elif dimension == "region_category":
        df["group"] = df["region"] + " / " + df["category"]
    else:
        df["group"] = df[dimension]
    return df


def _aggregate(df: pd.DataFrame, metric: str) -> pd.Series:
    """active_customers is a stock: average of the monthly totals per group; everything else is a flow: sum."""
    if metric == "active_customers":
        per_month = df.groupby(["group", "month"])[metric].sum().reset_index()
        return per_month.groupby("group")[metric].mean()
    return df.groupby("group")[metric].sum()


def _compare_frame(ctx: RunContext, a: CompareArgs) -> pd.DataFrame:
    sa, ea = _bounds(a.period_a.start, a.period_a.end)
    sb, eb = _bounds(a.period_b.start, a.period_b.end)
    ga = _aggregate(_frame(ctx, a.metric, sa, ea, a.dimension), a.metric)
    gb = _aggregate(_frame(ctx, a.metric, sb, eb, a.dimension), a.metric)
    out = pd.concat([ga.rename("a"), gb.rename("b")], axis=1).fillna(0.0)
    out["change"] = out["b"] - out["a"]
    out["pct"] = out.apply(lambda r: (r["change"] / r["a"] * 100.0) if r["a"] else None, axis=1)
    return out


def _r(x: float | None, n: int = 2) -> float | None:
    return None if x is None or pd.isna(x) else round(float(x), n)


def _label(p: Period) -> str:
    return p.start if p.start == p.end else f"{p.start}..{p.end}"


def stats_compare(ctx: RunContext, args: CompareArgs) -> ToolResult:
    df = _compare_frame(ctx, args).sort_values("change")
    la, lb = _label(args.period_a), _label(args.period_b)
    total_a, total_b = float(df["a"].sum()), float(df["b"].sum())
    if args.metric == "active_customers" and args.dimension != "none":
        pass  # a sum of group averages is still the average total
    rows = [[g, _r(r.a), _r(r.b), _r(r.change), _r(r.pct, 1)] for g, r in df.iterrows()]
    if args.dimension != "none":
        rows.append(["TOTAL", _r(total_a), _r(total_b), _r(total_b - total_a), _r((total_b - total_a) / total_a * 100, 1) if total_a else None])
    cols = ["group", f"{args.metric} {la}", f"{args.metric} {lb}", "change", "change_pct"]
    chart = {"type": "bar", "x": [str(g) for g in df.index], "series": [{"name": la, "values": [float(v) for v in df["a"]]},
                                                                      {"name": lb, "values": [float(v) for v in df["b"]]}]}
    ev = table_evidence("STATS", f"{args.metric} by {args.dimension}: {la} vs {lb}", cols, rows,
                        source={"table": METRIC_TABLE[args.metric]}, chart=chart)
    return ToolResult(f"compared {args.metric} by {args.dimension}: {len(rows)} row(s)", wrap_untrusted(text_table(cols, rows, 25), "stats_compare"), [ev])


def stats_contribution(ctx: RunContext, args: ContributionArgs) -> ToolResult:
    df = _compare_frame(ctx, args)
    net = float(df["change"].sum())
    df = df.reindex(df["change"].abs().sort_values(ascending=False).index)
    la, lb = _label(args.period_a), _label(args.period_b)
    rows = [[g, _r(r.a), _r(r.b), _r(r.change), _r(r.pct, 1), _r(r.change / net * 100, 1) if net else None] for g, r in df.iterrows()]
    cols = ["group", f"{args.metric} {la}", f"{args.metric} {lb}", "change", "change_pct", "share_of_net_change_pct"]
    chart = {"type": "bar", "x": [str(g) for g in df.index], "series": [{"name": f"{args.metric} change", "values": [float(v) for v in df["change"]]}]}
    ev = table_evidence("STATS", f"Contribution to {args.metric} change by {args.dimension}: {la} vs {lb}", cols, rows,
                        source={"table": METRIC_TABLE[args.metric]}, chart=chart)
    head = f"Net change in {args.metric}: {net:,.2f}. Share is of the net change; a negative share means the group grew against the trend.\n"
    return ToolResult(f"net change {net:,.2f}; top driver: {rows[0][0] if rows else 'n/a'}", wrap_untrusted(head + text_table(cols, rows, 25), "stats_contribution"), [ev])


def stats_anomaly(ctx: RunContext, args: AnomalyArgs) -> ToolResult:
    s, e = _bounds(args.start, args.end)
    df = _frame(ctx, args.metric, s, e, args.dimension)
    agg = "mean" if args.metric == "active_customers" else "sum"
    monthly = df.groupby(["group", "month"])[args.metric].agg("sum").reset_index() if agg == "sum" else df.groupby(["group", "month"])[args.metric].sum().reset_index()
    out: list[list[object]] = []
    series: dict[str, dict[str, float]] = {}
    for g, part in monthly.groupby("group"):
        vals = part[args.metric].astype(float)
        series[str(g)] = dict(zip(part["month"], vals, strict=True))
        if len(vals) < 4 or vals.std(ddof=1) == 0:
            continue
        z = (vals - vals.mean()) / vals.std(ddof=1)
        for m, v, zz in zip(part["month"], vals, z, strict=True):
            if abs(zz) >= args.z_threshold:
                out.append([str(g), m, _r(v), _r(vals.mean()), _r(zz, 2)])
    out.sort(key=lambda r: -abs(float(r[4])))  # type: ignore[arg-type]
    cols = ["group", "month", args.metric, "group_mean", "z_score"]
    months = sorted({m for d in series.values() for m in d})
    top_groups = sorted(series, key=lambda g: -max(abs(float(r[4])) for r in out if r[0] == g) if any(r[0] == g for r in out) else 0)[:6]
    chart = {"type": "line", "x": months, "series": [{"name": g, "values": [float(series[g].get(m, 0.0)) for m in months]} for g in top_groups]}
    ev = table_evidence("STATS", f"Anomalies in {args.metric} by {args.dimension}, {args.start}..{args.end} (|z| >= {args.z_threshold})", cols, out,
                        source={"table": METRIC_TABLE[args.metric]}, chart=chart)
    obs = text_table(cols, out, 25) if out else f"No anomalies with |z| >= {args.z_threshold}."
    return ToolResult(f"{len(out)} anomalous point(s)", wrap_untrusted(obs, "stats_anomaly"), [ev] if out else [])
