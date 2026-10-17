"""data_analyst (AI-AG-05): ReAct tool loop over sql_query + stats tools; numeric evidence with tables and chart-ready series."""
from __future__ import annotations

from typing import Any

from app.agents.common import node
from app.agents.context import RunContext
from app.agents.nodes.researcher import run_agent_steps


@node("data_analyst")
def data_analyst(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    return run_agent_steps(state, ctx, "DATA_ANALYST", "data_analyst")
