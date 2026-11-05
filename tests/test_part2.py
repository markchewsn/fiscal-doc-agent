import asyncio
import json

import pytest
from langchain_core.messages import AIMessage

from fiscal_doc_agent.dates import normalize_dates
from fiscal_doc_agent.parsing import ROOT
from fiscal_doc_agent.part2 import classify_dates, mcp_tools, run_part2, skill_tool
from fakes import FakeChat


@pytest.mark.parametrize(
    ("text", "iso"),
    [
        ("Distributed on Budget Day: 16 February 2024", ["2024-02-16"]),
        ("15 February 2008", ["2008-02-15"]),
        ("dies after 15 February 2008.", ["2008-02-15"]),
        ("16 Feb 2024", ["2024-02-16"]),
        ("16/02/2024", ["2024-02-16"]),  # Singapore day-first
        ("2024-02-03", ["2024-02-03"]),  # ISO stays year-month-day
        ("Financial Year 2023 runs 1 April 2023 to 31 March 2024.", ["2023-04-01", "2024-03-31"]),
        ("from 2024-04-01 until 31/03/2025", ["2024-04-01", "2025-03-31"]),
    ],
)
def test_normalize_dates_returns_every_full_date_in_each_text(text, iso):
    assert normalize_dates([text]) == [iso]


def test_normalize_dates_handles_many_texts_and_texts_without_a_full_date():
    texts = ["16 February 2024", "February 2024", "no date here", "16 February", "FY2023",
             "1 April 2023 to 31 March 2024"]
    assert normalize_dates(texts) == [
        ["2024-02-16"], [], [], [], [], ["2023-04-01", "2024-03-31"],
    ]


DIST = "Distributed on Budget Day: 16 February 2024"
ESTATE = "15 February 2008"


RECORDS = [
    {"original_text": DIST, "normalized_date": "2024-02-16", "status": "Upcoming", "reasoning": "r1"},
    {"original_text": ESTATE, "normalized_date": "2008-02-15", "status": "Expired", "reasoning": "r2"},
]


def _call(name, i, **args):
    return {"name": name, "args": args, "id": f"c{i}"}


def _fake_model(*turns):
    mention = lambda text, page: {"text": text, "evidence": {"page": page, "quote": text}}
    return FakeChat(
        turns=list(turns),
        structured=[{"distribution_date": mention(DIST, 1), "estate_duty_date": mention(ESTATE, 36)}],
    )


NORMALIZE = AIMessage("", tool_calls=[_call("normalize_dates", 1, texts=[DIST, ESTATE])])
SUBMIT = AIMessage("", tool_calls=[_call("submit_dates", 3, records=RECORDS)])


def test_mcp_arm_normalises_through_mcp_server_visible_from_turn_one():
    model = _fake_model(NORMALIZE, SUBMIT)

    result = asyncio.run(run_part2("mcp", model))

    first_turn = model.tools_per_turn[0]
    assert "normalize_dates" in first_turn
    assert sorted(set(first_turn) - {"normalize_dates"}) == ["ls", "read_file", "submit_dates"]
    assert result["records"] == RECORDS
    assert model.turns == []  # run ends on submit, no closing turn
    assert set(result["usage"]) == {"extract", "agent"}


def test_premature_submit_is_rejected_and_agent_recovers_in_same_run():
    early = AIMessage("", tool_calls=[_call("submit_dates", 0, records=RECORDS)])
    model = _fake_model(early, NORMALIZE, SUBMIT)

    result = asyncio.run(run_part2("mcp", model))

    assert result["records"] == RECORDS
    assert model.turns == []


def test_run_without_submit_fails_loudly():
    model = _fake_model(NORMALIZE, AIMessage("all done"))
    with pytest.raises(RuntimeError, match="submit_dates"):
        asyncio.run(run_part2("mcp", model))


def test_period_gives_one_record_per_date_and_dates_must_match_tool_output():
    fy = "Financial Year 2023: 1 April 2023 to 31 March 2024"
    record = lambda iso: {"original_text": fy, "normalized_date": iso, "status": "Ongoing",
                          "reasoning": "r"}
    submit = lambda i, *isos: AIMessage("", tool_calls=[
        _call("submit_dates", i, records=[record(d) for d in isos])])
    model = _fake_model(
        AIMessage("", tool_calls=[_call("normalize_dates", 1, texts=[fy])]),
        submit(2, "2023-04-01", "2024-04-30"),  # made-up end date
        submit(3, "2023-04-01"),  # end date missing
        submit(4, "2023-04-01", "2024-03-31"),
    )

    records, _ = asyncio.run(classify_dates([{"original_text": fy, "context": ""}], model, "mcp"))

    assert records == [record("2023-04-01"), record("2024-03-31")]
    assert model.turns == []  # both bad submits were rejected, the good one ended the run


def test_committed_part2_mcp_output():
    out = json.loads((ROOT / "outputs" / "part2_mcp.json").read_text())
    by_date = {r["normalized_date"]: r for r in out["records"]}
    assert set(by_date) == {"2024-02-16", "2008-02-15"}
    assert by_date["2024-02-16"]["status"] == "Upcoming"
    estate = by_date["2008-02-15"]
    assert estate["status"] == "Expired"
    reasoning = estate["reasoning"].casefold()
    assert "in force" in reasoning or "in effect" in reasoning  # abolition rule still applies
    for r in out["records"]:
        assert set(r) == {"original_text", "normalized_date", "status", "reasoning"}

    pages = {name: m["evidence"]["page"] for name, m in out["mentions"].items()}
    assert pages == {"distribution_date": 1, "estate_duty_date": 36}

    demo = {r["normalized_date"]: r["status"] for r in out["robustness_demo"]}
    assert demo == {"2022-04-01": "Expired", "2023-03-31": "Expired",  # FY2022, ended
                    "2023-04-01": "Ongoing", "2024-03-31": "Ongoing",  # FY2023, active
                    "2024-04-01": "Upcoming", "2025-03-31": "Upcoming"}  # FY2024
    assert out["usage"]["agent"] and out["cost_usd"]["agent"] > 0


def test_skill_tool_matches_mcp_tool_so_only_delivery_differs():
    (mcp,) = asyncio.run(mcp_tools())
    skill = skill_tool()
    assert (skill.name, skill.description, skill.args) == (mcp.name, mcp.description, mcp.args)
    assert json.loads(skill.invoke({"texts": [DIST, "none"]})) == [["2024-02-16"], []]


READ_SKILL = AIMessage("", tool_calls=[
    _call("read_file", 0, file_path="/normalize-dates/SKILL.md", limit=1000)])


def test_skill_arm_sees_normalize_dates_only_after_reading_skill():
    model = _fake_model(READ_SKILL, NORMALIZE, SUBMIT)

    result = asyncio.run(run_part2("skill", model))

    before, after = model.tools_per_turn[:2]
    assert sorted(before) == ["ls", "read_file", "submit_dates"]
    assert sorted(after) == ["ls", "normalize_dates", "read_file", "submit_dates"]
    assert result["records"] == RECORDS  # same contract as the MCP arm on the same script
    assert model.turns == []


def test_skill_arm_cannot_call_normalize_dates_before_reading_skill():
    too_early = AIMessage("", tool_calls=[_call("normalize_dates", 9, texts=[DIST, ESTATE])])
    model = _fake_model(too_early, READ_SKILL, NORMALIZE, SUBMIT)

    result = asyncio.run(run_part2("skill", model))

    assert result["records"] == RECORDS  # first call failed as unknown tool, agent recovered
    assert "normalize_dates" not in model.tools_per_turn[0]


def test_committed_skill_arm_output_agrees_with_mcp_arm():
    load = lambda arm: json.loads((ROOT / "outputs" / f"part2_{arm}.json").read_text())
    mcp, skill = load("mcp"), load("skill")
    statuses = lambda out: {r["normalized_date"]: r["status"]
                            for r in out["records"] + out["robustness_demo"]}
    assert skill["arm"] == "skill"
    assert statuses(skill) == statuses(mcp)
    for r in skill["records"]:
        assert set(r) == {"original_text", "normalized_date", "status", "reasoning"}
    assert skill["cost_usd"]["agent"] > 0
    assert "agree across arms: **yes**" in (ROOT / "outputs" / "part2_comparison.md").read_text()
