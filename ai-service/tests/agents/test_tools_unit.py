"""Registry (AI-TL-01), catalogue (AI-TL-05), stats tools reproduce the planted story (AI-TL-03/AI-DM-01), confidence math (AI-AG-07/08)."""
import json
import threading
from pathlib import Path

import pytest

from app.agents import confidence as cf
from app.agents.testing import ScriptedLlm
from app.api.schemas import ActionType, Risk
from app.tools import action_catalogue as cat
from app.tools.builder import build_registry
from app.tools.registry import READ_EXTERNAL, READ_INTERNAL, RISK_TAGS, ToolError
from tests.agents.harness import make_runtime, mkreq

FACTS = json.loads((Path(__file__).resolve().parents[2] / "app" / "evals" / "seed" / "facts.json").read_text())


def _ctx(biz):
    return make_runtime(biz, ScriptedLlm({})).make_ctx(user_id=1, investigation_id=1, thread_id="t", options=mkreq().options, now="x",
                                                      emit=lambda e: None, cancel=threading.Event())


# --------------------------------------------------------------------------------- registry
def test_registry_metadata_and_no_write_tools(biz):
    reg = build_registry(biz.settings, web_enabled=True)
    assert set(reg.names()) == {"rag_search", "sql_query", "web_search", "stats_compare", "stats_contribution", "stats_anomaly", "recall_memory"}
    for s in reg.specs.values():
        assert s.risk_tag in RISK_TAGS == {READ_INTERNAL, READ_EXTERNAL}
        assert s.timeout_s > 0 and s.budget > 0 and s.allowed_agents and s.args_model
    assert reg.specs["web_search"].risk_tag == READ_EXTERNAL
    assert not any("write" in n or "execute" in n or "approve" in n or "delete" in n for n in reg.names())


def test_web_search_only_registered_when_enabled(biz):
    assert "web_search" not in build_registry(biz.settings, web_enabled=False).names()
    assert "web_search" in build_registry(biz.settings, web_enabled=True).describe_for("RESEARCHER")


def test_validation_errors_are_readable(biz):
    reg = build_registry(biz.settings, web_enabled=False)
    with pytest.raises(ToolError, match="Unknown tool"):
        reg.validate("RESEARCHER", "drop_tables", {})
    with pytest.raises(ToolError, match="not available to RESEARCHER"):
        reg.validate("RESEARCHER", "sql_query", {"sql": "SELECT 1"})                     # allowed agents enforced
    with pytest.raises(ToolError, match="Invalid arguments"):
        reg.validate("DATA_ANALYST", "stats_compare", {"metric": "nonsense"})
    with pytest.raises(ToolError, match="JSON object"):
        reg.validate("DATA_ANALYST", "sql_query", "SELECT 1")


def test_call_budget_is_enforced_per_run(biz):
    from app.tools.registry import RunTools
    ctx = _ctx(biz)
    tools = RunTools(build_registry(biz.settings, web_enabled=False))
    for _ in range(6):
        tools.execute(ctx, "DATA_ANALYST", "stats_anomaly", {"metric": "units", "dimension": "none", "start": "2026-01", "end": "2026-09"})
    with pytest.raises(ToolError, match="budget"):
        tools.execute(ctx, "DATA_ANALYST", "stats_anomaly", {"metric": "units", "dimension": "none", "start": "2026-01", "end": "2026-09"})


def test_tool_timeout_enforced(biz):
    import time
    from dataclasses import replace

    from pydantic import BaseModel

    from app.tools.registry import RunTools, ToolRegistry, ToolResult, ToolSpec

    class A(BaseModel):
        pass
    spec = ToolSpec("slow", "d", A, READ_INTERNAL, frozenset({"RESEARCHER"}), 0.2, 3, lambda c, a: (time.sleep(1.5), ToolResult("x", "x"))[1])
    with pytest.raises(ToolError) as e:
        RunTools(ToolRegistry([spec])).execute(_ctx(biz), "RESEARCHER", "slow", {})
    assert e.value.transient and "timed out" in e.value.reason
    _ = replace


# --------------------------------------------------------------------------------- action catalogue
def test_catalogue_covers_all_six_actions_with_fixed_risk():
    low = {ActionType.FLAG_FOR_REVIEW, ActionType.CREATE_FOLLOWUP_TASK, ActionType.SAVE_INSIGHT}
    for t in ActionType:
        assert cat.risk_of(t) == (Risk.LOW if t in low else Risk.HIGH)


@pytest.mark.parametrize("forged", ["LOW", "low", None, 0, "NONE", {"x": 1}])
def test_llm_supplied_risk_is_ignored(forged):
    p = cat.validate_proposal({"type": "ADJUST_PRICE", "params": {"productId": 1, "changePct": 5}, "risk": forged})
    assert p.risk == Risk.HIGH
    p = cat.validate_proposal({"type": "FLAG_FOR_REVIEW", "params": {"subject": "a", "reason": "b"}, "risk": "HIGH"})
    assert p.risk == Risk.LOW


@pytest.mark.parametrize("raw", [
    {"type": "ADJUST_PRICE", "params": {"productId": 1, "changePct": 31}}, {"type": "ADJUST_PRICE", "params": {"productId": 1, "changePct": 0}},
    {"type": "ADJUST_PRICE", "params": {"productId": 1}}, {"type": "ADJUST_PRICE", "params": {"productId": 1, "changePct": 5, "extra": 1}},
    {"type": "PAUSE_CAMPAIGN", "params": {"regionId": 1, "channel": "Social", "weeks": 0}},
    {"type": "REALLOCATE_BUDGET", "params": {"fromRegionId": 1, "toRegionId": 1, "amount": 10}},
    {"type": "REALLOCATE_BUDGET", "params": {"fromRegionId": 1, "toRegionId": 2, "amount": -5}},
    {"type": "CREATE_FOLLOWUP_TASK", "params": {"title": "x", "ownerRole": "CEO", "dueInDays": 3}},
    {"type": "EXECUTE_SQL", "params": {}}, {"type": ""}, {}, "ADJUST_PRICE", None,
])
def test_invalid_or_unknown_proposals_rejected(raw):
    with pytest.raises(cat.ActionRejected):
        cat.validate_proposal(raw)


def test_valid_proposals_use_camel_case_wire_params():
    p = cat.validate_proposal({"type": "REALLOCATE_BUDGET", "params": {"from_region_id": 1, "toRegionId": 2, "amount": 100}})
    assert p.params == {"fromRegionId": 1, "toRegionId": 2, "amount": 100.0}
    assert cat.fingerprint("ADJUST_PRICE", {"a": 1}) == cat.fingerprint("ADJUST_PRICE", {"a": 1}) != cat.fingerprint("ADJUST_PRICE", {"a": 2})


# --------------------------------------------------------------------------------- stats tools reproduce the planted story
Q1, Q2 = {"start": "2026-01", "end": "2026-03"}, {"start": "2026-04", "end": "2026-06"}


def _rows(res):
    d = res.evidence[0].data
    return d["columns"], {r[0]: r for r in d["rows"]}


def test_stats_compare_total_matches_the_seed_facts(biz):
    from app.tools.stats_tool import CompareArgs, stats_compare
    res = stats_compare(_ctx(biz), CompareArgs(metric="revenue", dimension="region", period_a=Q1, period_b=Q2))
    cols, rows = _rows(res)
    assert rows["TOTAL"][1] == pytest.approx(FACTS["total_revenue"]["q1_2026"]) and rows["TOTAL"][2] == pytest.approx(FACTS["total_revenue"]["q2_2026"])
    assert rows["TOTAL"][4] == pytest.approx(FACTS["total_revenue"]["pct"], abs=0.1)
    assert rows["West"][4] < rows["South"][4] < 0 < rows["North"][4] or rows["West"][4] < 0                  # West fell hardest
    assert res.evidence[0].chart["type"] == "bar" and len(res.evidence[0].chart["series"]) == 2


def test_stats_contribution_finds_west_home_as_primary_driver(biz):
    from app.tools.stats_tool import ContributionArgs, stats_contribution
    res = stats_contribution(_ctx(biz), ContributionArgs(metric="revenue", dimension="region_category", period_a=Q1, period_b=Q2))
    cols, rows = _rows(res)
    ordered = [r[0] for r in res.evidence[0].data["rows"]]
    assert ordered[0] == "West / Home"                                                      # primary cause
    assert rows["West / Home"][5] == pytest.approx(FACTS["groups"]["West/Home"]["share_of_net_change_pct"], abs=0.1) and rows["West / Home"][5] >= 60
    assert rows["North / Electronics"][4] >= 10 and rows["North / Electronics"][5] < 0     # the region that grew offsets the decline
    assert abs(rows["East / Apparel"][5]) < 15                                              # red herring is small
    south = sum(r[3] for k, r in rows.items() if k.startswith("South"))
    assert south == pytest.approx(FACTS["south_region_change"], abs=1)                      # secondary cause is real and material


def test_stats_marketing_and_customers_tell_the_secondary_story(biz):
    from app.tools.stats_tool import CompareArgs, stats_compare
    res = stats_compare(_ctx(biz), CompareArgs(metric="marketing_spend", dimension="region", period_a=Q1, period_b=Q2))
    _, rows = _rows(res)
    assert rows["South"][4] == pytest.approx(FACTS["south_marketing"]["pct"], abs=0.2) and rows["South"][4] < -25
    assert abs(rows["West"][4]) < 10                                                        # West marketing did not change: not the cause there
    res = stats_compare(_ctx(biz), CompareArgs(metric="churned_customers", dimension="region", period_a=Q1, period_b=Q2))
    _, rows = _rows(res)
    assert rows["West"][4] > 20                                                             # churn spike in the West (stock-out)


def test_red_herring_is_seasonal_in_2025_too(biz):
    from app.tools.stats_tool import CompareArgs, stats_compare
    res = stats_compare(_ctx(biz), CompareArgs(metric="revenue", dimension="region_category",
                                               period_a={"start": "2025-01", "end": "2025-03"}, period_b={"start": "2025-04", "end": "2025-06"}))
    _, rows = _rows(res)
    assert rows["East / Apparel"][4] == pytest.approx(FACTS["east_apparel_q2_vs_q1_2025_pct"], abs=0.1) and rows["East / Apparel"][4] < -2


def test_stats_anomaly_flags_the_west_home_stockout_months(biz):
    from app.tools.stats_tool import AnomalyArgs, stats_anomaly
    res = stats_anomaly(_ctx(biz), AnomalyArgs(metric="revenue", dimension="region_category", start="2025-01", end="2026-09", z_threshold=2.0))
    flagged = {(r[0], r[1]) for r in res.evidence[0].data["rows"]}
    assert ("West / Home", "2026-05") in flagged and ("West / Home", "2026-06") in flagged
    assert all(abs(r[4]) >= 2.0 for r in res.evidence[0].data["rows"])
    assert res.evidence[0].chart["type"] == "line"


def test_stats_errors_are_readable(biz):
    from app.tools.stats_tool import CompareArgs, stats_compare
    with pytest.raises(ToolError, match="not available for marketing_spend"):
        stats_compare(_ctx(biz), CompareArgs(metric="marketing_spend", dimension="product", period_a=Q1, period_b=Q2))
    with pytest.raises(ToolError, match="before period start"):
        stats_compare(_ctx(biz), CompareArgs(metric="revenue", period_a={"start": "2026-05", "end": "2026-01"}, period_b=Q2))
    with pytest.raises(ToolError, match="No data"):
        stats_compare(_ctx(biz), CompareArgs(metric="revenue", period_a={"start": "2019-01", "end": "2019-03"}, period_b=Q2))


# --------------------------------------------------------------------------------- confidence model (contract section 9)
def test_claim_confidence_formula_and_caps():
    assert cf.claim_confidence(1.0, 2, 1.0, "VERIFIED") == 1.0
    assert cf.claim_confidence(0.8, 1, 0.5, "VERIFIED") == pytest.approx(0.5 * 0.8 + 0.3 * 0.5 + 0.2 * 0.5)
    assert cf.claim_confidence(1.0, 5, 1.0, "CONTRADICTED") == 0.3 and cf.claim_confidence(1.0, 5, 1.0, "UNSUPPORTED") == 0.4
    assert cf.claim_confidence(0.0, 0, 0.0, "UNSUPPORTED") == 0.0
    assert cf.claim_confidence(7, 9, 9, "VERIFIED") == 1.0                       # clamped


def test_agreement_and_independent_sources():
    assert [cf.agreement(n) for n in (0, 1, 2, 3)] == [0.0, 0.5, 1.0, 1.0]
    evs = [{"kind": "DOCUMENT", "source": {"documentId": 1}}, {"kind": "DOCUMENT", "source": {"documentId": 1}}, {"kind": "DOCUMENT", "source": {"documentId": 2}},
           {"kind": "SQL", "source": {"sql": "SELECT 1"}}, {"kind": "SQL", "source": {"sql": "SELECT 1"}}, {"kind": "WEB", "source": {"url": "https://a.com/x"}},
           {"kind": "WEB", "source": {"url": "https://a.com/y"}}, {"kind": "WEB", "source": {"url": "https://b.com/y"}}]
    assert cf.independent_sources(evs) == 5            # doc1, doc2, sql, a.com, b.com


def test_quality_sql_is_one_documents_use_score():
    assert cf.quality([{"kind": "SQL"}, {"kind": "STATS"}]) == 1.0
    assert cf.quality([{"kind": "DOCUMENT", "score": 0.4}, {"kind": "SQL"}]) == pytest.approx(0.7)
    assert cf.quality([{"kind": "WEB", "score": None}]) == 0.5 and cf.quality([]) == 0.0


def test_overall_weights_key_claims_double():
    claims = [{"isKey": True, "confidence": 0.9}, {"isKey": False, "confidence": 0.3}]
    assert cf.overall_confidence(claims) == pytest.approx((2 * 0.9 + 0.3) / 3, abs=1e-3)
    assert cf.overall_confidence([]) == 0.0


@pytest.mark.parametrize("overall,loop,mx,expected", [(0.7, 0, 3, "ACCEPT"), (0.95, 3, 3, "ACCEPT"), (0.69, 0, 3, "LOOP"), (0.2, 2, 3, "LOOP"),
                                                      (0.69, 3, 3, "ACCEPT_LOW_CONFIDENCE"), (0.0, 5, 5, "ACCEPT_LOW_CONFIDENCE")])
def test_decision_branches(overall, loop, mx, expected):
    assert cf.decide(overall, 0.7, loop, mx) == expected


def test_status_guard_and_weakest_claims():
    assert cf.normalise_status("VERIFIED", 0.9, False) == "UNSUPPORTED"          # no evidence can never be verified
    assert cf.normalise_status("VERIFIED", 0.3, True) == "UNSUPPORTED"           # verdict contradicted by its own support score
    assert cf.normalise_status("CONTRADICTED", 0.0, True) == "CONTRADICTED" and cf.normalise_status("VERIFIED", 0.8, True) == "VERIFIED"
    assert cf.normalise_status("nonsense", 0.9, True) == "UNSUPPORTED"
    claims = [{"claimKey": "c1", "isKey": False, "status": "UNSUPPORTED", "confidence": 0.1}, {"claimKey": "c2", "isKey": True, "status": "UNSUPPORTED", "confidence": 0.3},
              {"claimKey": "c3", "isKey": True, "status": "VERIFIED", "confidence": 0.9}, {"claimKey": "c4", "isKey": True, "status": "VERIFIED", "confidence": 0.6}]
    assert [c["claimKey"] for c in cf.weakest_claims(claims, 0.7)] == ["c2", "c4", "c1"]        # key claims first, then lowest confidence
