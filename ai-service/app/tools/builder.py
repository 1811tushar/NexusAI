"""Builds the tool registry. web_search is registered only when the run allows it (options.webSearch AND WEB_SEARCH_ENABLED)."""
from __future__ import annotations

from typing import Any

from app.tools.memory_tool import MemArgs, recall_memory
from app.tools.rag_tool import RagArgs, rag_search
from app.tools.registry import READ_EXTERNAL, READ_INTERNAL, ToolRegistry, ToolSpec
from app.tools.sql_tool import SqlArgs, run_sql
from app.tools.stats_tool import AnomalyArgs, CompareArgs, ContributionArgs, stats_anomaly, stats_compare, stats_contribution
from app.tools.web_tool import WebArgs, web_search

RESEARCHER, DATA_ANALYST = "RESEARCHER", "DATA_ANALYST"


def build_registry(settings: Any, *, web_enabled: bool, single_agent: bool = False) -> ToolRegistry:
    """single_agent=True (evaluation variant SINGLE_AGENT): ONE agent ('ANALYST') may call every tool; the tools themselves are unchanged."""
    r, d = frozenset({RESEARCHER}), frozenset({DATA_ANALYST})
    if single_agent:
        r = d = frozenset({"ANALYST"})
    specs = [
        ToolSpec("rag_search", "hybrid search over the company documents; returns cited passages", RagArgs, READ_INTERNAL, r, 20, 12, rag_search),
        ToolSpec("recall_memory", "this user's earlier investigation summaries relevant to a query", MemArgs, READ_INTERNAL, r, 15, 3, recall_memory),
        ToolSpec("sql_query", "one read-only SELECT over regions(id,name), products(id,sku,name,category,unit_price,unit_cost), "
                              "sales(sale_month,region_id,product_id,units,revenue,cost), marketing_spend(month,region_id,channel,spend), "
                              "customer_metrics(month,region_id,active_customers,new_customers,churned_customers)",
                 SqlArgs, READ_INTERNAL, d, max(8.0, settings.sql_timeout_ms / 1000 + 3), 12, run_sql),
        ToolSpec("stats_compare", "period over period change (absolute and %) of a metric, optionally by region/product/category", CompareArgs,
                 READ_INTERNAL, d, 20, 8, stats_compare),
        ToolSpec("stats_contribution", "which region/product/category drove a metric's change, with share of the net change", ContributionArgs,
                 READ_INTERNAL, d, 20, 8, stats_contribution),
        ToolSpec("stats_anomaly", "z-score anomaly flags on a monthly metric series", AnomalyArgs, READ_INTERNAL, d, 20, 6, stats_anomaly),
    ]
    if web_enabled:
        specs.append(ToolSpec("web_search", "web search (external); only a short sub-task query is sent", WebArgs, READ_EXTERNAL, r, 20, 4, web_search))
    return ToolRegistry(specs)
