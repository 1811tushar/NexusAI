"""web_search tool (AI-TL-04). Registered ONLY when options.webSearch AND WEB_SEARCH_ENABLED. Tavily when a key exists, `ddgs` fallback.
Only the sub-task query text is sent; it is PII-redacted first (ADD-GR-02) and capped at 200 chars. Returns title/snippet/URL/domain as WEB evidence."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from app.agents.injection import looks_like_injection, wrap_untrusted
from app.core.pii import redact
from app.tools.registry import EvidenceDraft, ToolError, ToolResult

if TYPE_CHECKING:
    from app.agents.context import RunContext


class WebArgs(BaseModel):
    query: str = Field(min_length=3, max_length=200)


def default_web_search(settings: Any) -> Any:
    def search(query: str, n: int) -> list[dict[str, Any]]:
        key = settings.tavily_api_key.get_secret_value() if getattr(settings, "tavily_api_key", None) else None
        if key:
            from tavily import TavilyClient
            res = TavilyClient(api_key=key).search(query, max_results=n)
            return [{"title": r.get("title", ""), "url": r.get("url", ""), "content": r.get("content", ""), "score": r.get("score")} for r in res.get("results", [])]
        from ddgs import DDGS
        return [{"title": r.get("title", ""), "url": r.get("href", ""), "content": r.get("body", ""), "score": None} for r in DDGS().text(query, max_results=n)]
    return search


def web_search(ctx: RunContext, args: WebArgs) -> ToolResult:
    red = redact(args.query)
    if red.total:
        ctx.guardrail("TOOL", "REDACTED", "PII", red.to_guardrail_detail() + " from the web query before it left the network.")
    query = red.text[:200]
    fault = ctx.faults.take("web_search") if ctx.faults else None
    if fault == "timeout":
        raise ToolError("Web search timed out.", transient=True)
    if fault in ("error", "outage"):
        raise ToolError("Web search provider is unavailable.", transient=True)
    fn = ctx.web_search_fn
    if fn is None:
        raise ToolError("Web search is not configured.")
    try:
        results = [] if fault == "empty" else fn(query, 5)
    except ToolError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ToolError(f"Web search provider error ({type(exc).__name__}).", transient=True) from exc
    ev: list[EvidenceDraft] = []
    parts: list[str] = []
    for r in results[:5]:
        url, content = str(r.get("url") or ""), str(r.get("content") or "")[:600]
        domain = urlparse(url).netloc.lower()
        if looks_like_injection(content):
            ctx.guardrail("TOOL", "FLAGGED", "PROMPT_INJECTION", f"A web result from {domain or 'unknown'} contains instruction-like text; treated as data only.")
        score = r.get("score")
        ev.append(EvidenceDraft("WEB", (str(r.get("title") or domain))[:250], content, {"url": url}, score=float(score) if isinstance(score, (int, float)) else 0.5))
        parts.append(f"[{r.get('title') or domain} - {domain}] {content}")
    return ToolResult(f"{len(ev)} web result(s)", wrap_untrusted("\n\n".join(parts) or "(no results)", "web_search results"), ev)
