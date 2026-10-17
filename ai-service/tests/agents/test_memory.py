"""AI-ME-01..03: recall scoring, per-user isolation, dedupe, PII/secret hygiene, useMemory=false."""
import math

import pytest

from app.agents.nodes.save_memory import sanitise_memory
from app.agents.testing import ScriptedLlm
from app.memory import long_term, scoring
from tests.agents.harness import make_runtime, mkreq, of, run, standard_script, types
from tests.agents.test_graph_paths import docs  # noqa: F401  (fixture)

S1 = "West Home revenue fell 45 percent in Q2 2026 versus Q1 because of a supplier stock-out."


def test_scoring_formula():
    assert scoring.recall_score(1.0, 0, 1.0) == pytest.approx(1.0)
    assert scoring.recall_score(0.8, 30, 0.5) == pytest.approx(0.5 * 0.8 + 0.3 * math.exp(-1) + 0.2 * 0.5)
    assert scoring.recency(0) == 1.0 and scoring.recency(60) < scoring.recency(30) < 1.0 and scoring.recency(-5) == 1.0
    assert 0.3 <= scoring.importance_for(0.0, 0, 3) < scoring.importance_for(0.9, 3, 3) <= 1.0


def test_save_recall_floor_and_access_tracking(clean_memories):
    b = clean_memories
    mid, dup = long_term.save(b.rw, b.embedder, 1, S1, investigation_id=7, importance=0.8)
    assert not dup
    hits = long_term.recall(b.rw, b.embedder, 1, "Why did West Home revenue fall in Q2 2026?")
    assert [h.id for h in hits] == [mid] and hits[0].source_investigation_id == 7 and hits[0].score > scoring.MIN_RELEVANCE * 0.5
    assert long_term.recall(b.rw, b.embedder, 1, "zebra quantum giraffe harmonica") == []          # relevance floor
    with b.rw.connection() as c:
        row = c.execute("SELECT access_count, last_accessed_at FROM ai.memories WHERE id = %s", (mid,)).fetchone()
    assert row["access_count"] == 1 and row["last_accessed_at"] is not None


def test_ranking_uses_recency_and_importance_and_top_five(clean_memories):
    b = clean_memories
    ids = []
    for i in range(7):
        mid, _ = long_term.save(b.rw, b.embedder, 1, f"West Home revenue Q2 2026 supplier stock-out finding number {i} unique{i}x", investigation_id=i, importance=0.2 + 0.1 * i)
        ids.append(mid)
    with b.rw.connection() as c:
        c.execute("UPDATE ai.memories SET created_at = now() - interval '400 days' WHERE id = %s", (ids[6],))   # the most important one is ancient
        c.commit()
    hits = long_term.recall(b.rw, b.embedder, 1, "West Home revenue Q2 2026 supplier stock-out finding")
    assert len(hits) == scoring.TOP_N == 5
    assert hits == sorted(hits, key=lambda h: (-h.score, h.id))
    assert ids[6] not in [h.id for h in hits[:2]]                                                    # old memory lost despite top importance


def test_per_user_isolation_everywhere(clean_memories):
    b = clean_memories
    mid, _ = long_term.save(b.rw, b.embedder, 1, S1, investigation_id=1, importance=0.9)
    assert long_term.recall(b.rw, b.embedder, 2, S1) == []
    rows, total = long_term.list_memories(b.rw, 2, 0, 20)
    assert rows == [] and total == 0
    assert long_term.delete_one(b.rw, 2, mid) == 0                       # cannot delete another user's memory
    assert long_term.delete_all(b.rw, 2) == 0
    mid2, dup = long_term.save(b.rw, b.embedder, 2, S1, investigation_id=2, importance=0.5)
    assert mid2 != mid and not dup                                       # same text for another user is NOT a duplicate of user 1's
    assert long_term.delete_all(b.rw, 2) == 1
    assert long_term.recall(b.rw, b.embedder, 1, S1)[0].id == mid        # user 1 untouched


@pytest.mark.parametrize("bad", [None, 0, -1, "1", True])
def test_user_id_is_mandatory(clean_memories, bad):
    b = clean_memories
    for fn in (lambda: long_term.recall(b.rw, b.embedder, bad, "x"), lambda: long_term.delete_all(b.rw, bad), lambda: long_term.list_memories(b.rw, bad, 0, 5),
               lambda: long_term.save(b.rw, b.embedder, bad, "text", investigation_id=1, importance=0.5)):
        with pytest.raises(ValueError):
            fn()


def test_dedupe_by_similarity(clean_memories):
    b = clean_memories
    a, d1 = long_term.save(b.rw, b.embedder, 1, S1, investigation_id=1, importance=0.4)
    c, d2 = long_term.save(b.rw, b.embedder, 1, S1, investigation_id=2, importance=0.9)
    assert a == c and not d1 and d2
    rows, total = long_term.list_memories(b.rw, 1, 0, 20)
    assert total == 1 and rows[0]["importance"] == pytest.approx(0.9)    # kept the higher importance


def test_listing_search_and_paging(clean_memories):
    b = clean_memories
    for i in range(5):
        long_term.save(b.rw, b.embedder, 1, f"memory about topic{i} alpha{i} distinct words {i * 7}", investigation_id=i, importance=0.5)
    rows, total = long_term.list_memories(b.rw, 1, 0, 2)
    assert len(rows) == 2 and total == 5
    rows, total = long_term.list_memories(b.rw, 1, 0, 20, q="topic3")
    assert total == 1 and "topic3" in rows[0]["summary"]


@pytest.mark.parametrize("text,gone", [
    ("Contact jane.doe@example.com for details", "jane.doe@example.com"), ("Card 4111 1111 1111 1111 was used", "4111 1111 1111 1111"),
    ("api_key=sk-abcdefghijklmnopqrstuvwxyz123456 leaked", "sk-abcdefghijklmnopqrstuvwxyz123456"), ("password: hunter2hunter2", "hunter2hunter2"),
    ("Authorization Bearer abcdefghijklmnopqrstuvwxyz0123", "abcdefghijklmnopqrstuvwxyz0123"),
])
def test_memory_text_is_sanitised(text, gone):
    clean, n = sanitise_memory(text)
    assert gone not in clean and n >= 1 and len(clean) <= 500


def test_full_run_saves_and_recalls_for_the_same_user_only(docs, clean_memories):  # noqa: F811
    b = clean_memories
    ev1 = run(make_runtime(b, ScriptedLlm(standard_script())), mkreq(useMemory=True, user_id=11))
    assert of(ev1, "memory_recalled")[0]["items"] == [] and of(ev1, "memory_saved")
    assert types(ev1).index("memory_recalled") < types(ev1).index("supervisor_routed") and types(ev1)[-2:] == ["memory_saved", "done"]
    q2 = "Why did West Home revenue fall in Q2 2026 versus Q1 due to the supplier stock-out?"   # (hashing embedder is lexical; real BGE needs less overlap)
    ev2 = run(make_runtime(b, ScriptedLlm(standard_script())), mkreq(q2, useMemory=True, user_id=11, investigation_id=2))
    items = of(ev2, "memory_recalled")[0]["items"]
    assert len(items) == 1 and "West Home" in items[0]["summary"]
    ev3 = run(make_runtime(b, ScriptedLlm(standard_script())), mkreq(q2, useMemory=True, user_id=12, investigation_id=3))
    assert of(ev3, "memory_recalled")[0]["items"] == []                  # another user never sees it


def test_use_memory_false_touches_nothing(docs, clean_memories):  # noqa: F811
    b = clean_memories
    ev = run(make_runtime(b, ScriptedLlm(standard_script())), mkreq(useMemory=False, user_id=21))
    assert "memory_recalled" not in types(ev) and "memory_saved" not in types(ev)
    assert long_term.list_memories(b.rw, 21, 0, 5)[1] == 0


def test_pii_in_memory_summary_is_redacted_before_storage(docs, clean_memories):  # noqa: F811
    b = clean_memories
    s = standard_script()
    s["memory_summary"] = {"summary": "West Home fell 45 percent; ask jane.doe@example.com or card 4111 1111 1111 1111 about the stock-out."}
    ev = run(make_runtime(b, ScriptedLlm(s)), mkreq(useMemory=True, user_id=31))
    saved = of(ev, "memory_saved")[0]["summary"]
    assert "jane.doe" not in saved and "4111" not in saved
    g = [x for x in of(ev, "guardrail_triggered") if x["action"] == "REDACTED" and x["stage"] == "OUTPUT"]
    assert g and "jane.doe" not in g[0]["detail"]
    rows, _ = long_term.list_memories(b.rw, 31, 0, 5)
    assert "jane.doe" not in rows[0]["summary"]


def test_no_memory_saved_when_nothing_verified(docs, clean_memories):  # noqa: F811
    b = clean_memories
    s = standard_script()
    s["verifier"] = lambda system, user, n: {"support": 0.0, "status": "UNSUPPORTED", "reason": "no"}
    ev = run(make_runtime(b, ScriptedLlm(s)), mkreq(useMemory=True, user_id=41, maxLoops=1))
    assert "memory_saved" not in types(ev) and long_term.list_memories(b.rw, 41, 0, 5)[1] == 0
