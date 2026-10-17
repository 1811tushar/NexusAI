import pytest

from app.agents.testing import ScriptedLlm
from tests.agents.harness import ingest_supplier_doc, make_runtime, mkreq, of, run, standard_script, types


@pytest.fixture
def docs(biz):
    biz.store.delete_document(501)
    ingest_supplier_doc(biz)
    return biz


def test_accept_path_event_order_and_report(docs):
    llm = ScriptedLlm(standard_script())
    rt = make_runtime(docs, llm)
    events = run(rt, mkreq())
    t = types(events)
    print(t)
    assert t[-1] == "done" and t.count("done") == 1 and "error" not in t
    assert t.index("supervisor_routed") < t.index("plan") < t.index("claims_drafted") < t.index("claim_verified") < t.index("confidence") < t.index("report_ready")
    done = of(events, "done")[0]
    assert done["status"] == "COMPLETED" and done["loopsUsed"] == 0 and done["usage"]["inputTokens"] > 0
    rr = of(events, "report_ready")[0]
    assert "## Limitations and failures" in rr["reportMarkdown"] and "[ev:" in rr["reportMarkdown"]
    print(rr["reportMarkdown"])
