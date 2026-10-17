"""Short-term memory + approval pause (AI-ME-01, AI-HL-01): LangGraph AsyncPostgresSaver keyed by thread_id, tables in schema `ai` (the connection's
search_path is `ai,public`, owner ai_rw). The saver owns its own async pool; main.py stores the returned saver in app.state.checkpointer.
Windows note: psycopg async needs the SelectorEventLoop; run uvicorn WITHOUT --reload there, or use Docker (Linux)."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.core.config import Settings
from app.core.db import conninfo

log = logging.getLogger(__name__)


async def setup_checkpointer(settings: Settings, rw_pool: Any) -> Any:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    if type(asyncio.get_running_loop()).__name__ == "ProactorEventLoop":
        raise RuntimeError("The Postgres checkpointer needs the asyncio SelectorEventLoop (Windows default is Proactor). "
                           "Run uvicorn without --reload, or use the Docker image.")
    pool = AsyncConnectionPool(
        conninfo(settings, "rw"), min_size=1, max_size=max(2, min(settings.db_pool_max, 8)), open=False, name="ai_checkpointer",
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row, "options": "-c search_path=ai,public"})
    await pool.open(wait=True, timeout=30)
    saver = AsyncPostgresSaver(pool)
    await saver.setup()                                    # creates checkpoint tables if missing (idempotent)
    saver._nexus_pool = pool                               # type: ignore[attr-defined]  closed in close_checkpointer
    log.info("checkpointer ready (AsyncPostgresSaver, schema ai)")
    return saver


async def close_checkpointer(checkpointer: Any | None) -> None:
    pool = getattr(checkpointer, "_nexus_pool", None)
    if pool is not None:
        await pool.close()
