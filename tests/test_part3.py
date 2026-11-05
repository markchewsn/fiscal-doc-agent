import json
import re

import pytest
from langchain_core.messages import AIMessage

from fakes import FakeChat
from fiscal_doc_agent.parsing import ROOT
from fiscal_doc_agent.part3 import read_page, run_graph, search_document, sum_amounts


def test_search_document_ranks_future_energy_fund_pages_first():
    hits = search_document.invoke({"query": "Future Energy Fund", "k": 3})
    assert {h["page"] for h in hits} == {16, 18, 20}
    assert all(h["snippet"] for h in hits)


def test_read_page_returns_that_page_and_rejects_out_of_range():
    assert "Table 2.4" in read_page.invoke({"page": 20})
    assert "1 to 37" in read_page.invoke({"page": 99})


def test_sum_amounts_is_exact_decimal_sum():
    assert sum_amounts.invoke({"values": [6.0, 5.0, 2.0, 2.0, 2.0, 1.8, 1.0, 0.5, 0.05, 0.002]}) == 20.352
    assert sum_amounts.invoke({"values": [0.1, 0.2]}) == 0.3


def _call(name, i, **args):
    return {"name": name, "args": args, "id": f"c{i}"}


def _route(next_agent, reason):
    return {"next": next_agent, "reason": reason}


def test_supervisor_routes_each_agent_via_command_and_synthesises_on_finish():
    model = FakeChat(
        structured=[_route("revenue_agent", "need revenue streams"),
                    _route("expenditure_agent", "need Future Energy Fund support"),
                    _route("FINISH", "both parts answered")],
        turns=[AIMessage("", tool_calls=[_call("search_document", 1, query="revenue")]),
               AIMessage("Revenue findings"),
               AIMessage("", tool_calls=[_call("sum_amounts", 2, values=[5.0, 6.0])]),
               AIMessage("Expenditure findings"),
               AIMessage("Final comprehensive answer")],
    )

    result = run_graph("supervisor", "main question", model)

    assert result["answer"] == "Final comprehensive answer"
    assert model.turns == [] and model.structured == []
    assert [(e["type"], e.get("agent") or e.get("next")) for e in result["trace"]] == [
        ("route", "revenue_agent"),
        ("tool_call", "revenue_agent"),
        ("agent_answer", "revenue_agent"),
        ("route", "expenditure_agent"),
        ("tool_call", "expenditure_agent"),
        ("agent_answer", "expenditure_agent"),
        ("route", "FINISH"),
        ("final_answer", None),
    ]
    routes = [e for e in result["trace"] if e["type"] == "route"]
    assert [r["reason"] for r in routes] == ["need revenue streams",
                                             "need Future Energy Fund support",
                                             "both parts answered"]
    tool_calls = [e for e in result["trace"] if e["type"] == "tool_call"]
    assert tool_calls[0]["tool"] == "search_document" and tool_calls[0]["result"]
    assert tool_calls[1]["tool"] == "sum_amounts" and tool_calls[1]["result"] == "11.0"

    bound = {tuple(sorted(t)) for t in model.tools_per_turn}
    assert bound == {("read_page", "search_document"),  # revenue agent
                     ("read_page", "search_document", "sum_amounts")}  # expenditure agent
    # The expenditure agent and the synthesis both see earlier agents' findings.
    assert "Revenue findings" in str(model.seen[2])
    synthesis = str(model.seen[-1])
    assert "Revenue findings" in synthesis and "Expenditure findings" in synthesis
    # Usage reaches inside the nested agents: 4 agent turns + synthesis (the fake's
    # structured routing outputs bypass the model, so they are not counted here).
    assert result["llm_calls"] == 5
    assert set(result) >= {"answer", "trace", "usage", "llm_calls", "latency_s"}


def test_run_graph_rejects_unknown_kind():
    with pytest.raises(ValueError):
        run_graph("mesh", "q", FakeChat(turns=[]))


def test_committed_supervisor_output():
    out = json.loads((ROOT / "outputs" / "part3_supervisor.json").read_text())
    assert out["graph"] == "supervisor" and len(out["runs"]) == 4
    main = out["runs"][0]
    assert main["query"].startswith("What are the key government revenue streams")
    answer = main["answer"]
    fef = r"Future Energy Fund[^.\n]*\$5(\.0)? billion|\$5(\.0)? billion[^.\n]*Future Energy Fund"
    assert re.search(fef, answer)
    assert "energy transition" in answer.casefold().replace("-", " ")
    for stream in (("Corporate Income Tax", "CIT"), ("Goods and Services Tax", "GST"),
                   ("Personal Income Tax", "PIT")):
        assert any(name in answer for name in stream)
    assert re.search(r"\d+\.\d+ billion", answer)  # streams come with figures

    for run in out["runs"]:
        routes = [e for e in run["trace"] if e["type"] == "route"]
        assert routes and all(r["reason"] for r in routes) and routes[-1]["next"] == "FINISH"
        assert any(e["type"] == "tool_call" for e in run["trace"])
        assert "error" not in run, run.get("error")
        assert run["answer"] and run["llm_calls"] > 0 and run["cost_usd"]
    agents = {e["next"] for e in main["trace"] if e["type"] == "route"}
    assert agents == {"revenue_agent", "expenditure_agent", "FINISH"}
    trace_md = (ROOT / "outputs" / "part3_supervisor.md").read_text()
    assert "supervisor -> revenue_agent" in trace_md and "Final answer" in trace_md
