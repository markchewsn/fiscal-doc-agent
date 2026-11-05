import json
import re

import pytest
from langchain_core.messages import AIMessage

from fakes import FakeChat
from fiscal_doc_agent.parsing import ROOT
from fiscal_doc_agent.part3 import AGENTS, read_page, run_graph, search_document, sum_amounts


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
    # Usage counts the agents' own LLM calls too: 4 agent turns + synthesis (the fake's
    # structured routing outputs bypass the model, so they are not counted here).
    assert result["llm_calls"] == 5
    assert set(result) >= {"answer", "trace", "usage", "llm_calls", "latency_s"}


def test_swarm_hands_off_agent_to_agent_and_last_agent_answers():
    model = FakeChat(
        structured=[{"agent": "revenue_agent", "reason": "question opens on revenue"}],
        turns=[AIMessage("", tool_calls=[_call("search_document", 1, query="revenue")]),
               AIMessage("", tool_calls=[_call("transfer_to_expenditure_agent", 2,
                                               findings="Revenue findings",
                                               task="Find Future Energy Fund support")]),
               AIMessage("", tool_calls=[_call("sum_amounts", 3, values=[5.0, 6.0])]),
               AIMessage("Final swarm answer")],
    )

    result = run_graph("swarm", "main question", model)

    assert result["answer"] == "Final swarm answer"
    assert model.turns == [] and model.structured == []
    # No central hop: entry picks the first agent, then the agents hand off directly.
    assert [(e["type"], e.get("agent"), e.get("next")) for e in result["trace"]] == [
        ("entry", None, "revenue_agent"),
        ("tool_call", "revenue_agent", None),
        ("handoff", "revenue_agent", "expenditure_agent"),
        ("tool_call", "expenditure_agent", None),
        ("final_answer", "expenditure_agent", None),
    ]
    handoff = result["trace"][2]
    assert handoff["reason"] == "Find Future Energy Fund support"
    assert handoff["findings"] == "Revenue findings"
    assert result["trace"][3]["result"] == "11.0"

    # Same agents, prompts and tools as the supervisor graph, plus one handoff tool each.
    bound = {tuple(sorted(t)) for t in model.tools_per_turn}
    assert bound == {("read_page", "search_document", "transfer_to_expenditure_agent"),
                     ("read_page", "search_document", "sum_amounts",
                      "transfer_to_revenue_agent")}
    assert model.seen[0][0].content == AGENTS["revenue_agent"]["prompt"]
    assert model.seen[2][0].content == AGENTS["expenditure_agent"]["prompt"]
    # The peer is briefed with the handing-off agent's findings and task.
    assert "Revenue findings" in str(model.seen[2])
    assert "Find Future Energy Fund support" in str(model.seen[2])
    # 4 agent turns, no supervisor routes or synthesis (entry is a structured fake output).
    assert result["llm_calls"] == 4


def test_run_graph_rejects_unknown_kind():
    with pytest.raises(ValueError):
        run_graph("mesh", "q", FakeChat(turns=[]))


def _assert_main_answer(main):
    assert main["query"].startswith("What are the key government revenue streams")
    answer = main["answer"]
    fef = r"Future Energy Fund[^\n]*\$5(\.0)? ?(billion|b)\b|\$5(\.0)? ?(billion|b)\b[^\n]*Future Energy Fund"
    assert re.search(fef, answer)
    assert "energy transition" in answer.casefold().replace("-", " ")
    for stream in (("Corporate Income Tax", "CIT"), ("Goods and Services Tax", "GST"),
                   ("Personal Income Tax", "PIT")):
        assert any(name in answer for name in stream)
    assert re.search(r"\d+\.\d+ ?(billion|b)\b", answer)  # streams come with figures


def test_committed_supervisor_output():
    out = json.loads((ROOT / "outputs" / "part3_supervisor.json").read_text())
    assert out["graph"] == "supervisor" and len(out["runs"]) == 4
    main = out["runs"][0]
    _assert_main_answer(main)

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


def test_committed_swarm_output_and_comparison():
    out = json.loads((ROOT / "outputs" / "part3_swarm.json").read_text())
    supervisor = json.loads((ROOT / "outputs" / "part3_supervisor.json").read_text())
    assert out["graph"] == "swarm" and len(out["runs"]) == 4
    assert [r["query"] for r in out["runs"]] == [r["query"] for r in supervisor["runs"]]
    _assert_main_answer(out["runs"][0])
    for run in out["runs"]:
        assert "error" not in run, run.get("error")
        types = [e["type"] for e in run["trace"]]
        assert types[0] == "entry" and "route" not in types  # no central router
        assert types[-1] == "final_answer" and run["trace"][-1]["agent"]
        assert run["answer"] and run["llm_calls"] > 0 and run["cost_usd"]
    # Cross-agent queries hand off directly, agent to agent.
    for run in (out["runs"][0], out["runs"][3]):
        handoffs = [e for e in run["trace"] if e["type"] == "handoff"]
        assert [(h["agent"], h["next"]) for h in handoffs] == [
            ("revenue_agent", "expenditure_agent")]
        assert all(h["findings"] for h in handoffs)
        assert run["trace"][-1]["agent"] == "expenditure_agent"
    trace_md = (ROOT / "outputs" / "part3_swarm.md").read_text()
    assert "revenue_agent -> expenditure_agent** (direct handoff)" in trace_md

    table = (ROOT / "outputs" / "part3_comparison.md").read_text()
    assert "**Total supervisor**" in table and "**Total swarm**" in table
    assert table.count("| supervisor |") == 4 and table.count("| swarm |") == 4
