"""Part 2: extract two dates; an agent normalises them via a tool and classifies vs 2024-01-01."""

import importlib.util
import json
import sys
from functools import cache
from typing import Literal

from deepagents import (
    FilesystemMiddleware,
    GeneralPurposeSubagentProfile,
    HarnessProfile,
    create_deep_agent,
    register_harness_profile,
)
from deepagents._models import get_model_provider
from deepagents.backends import FilesystemBackend
from deepagents.middleware import SkillsMiddleware
from langchain_core.callbacks import get_usage_metadata_callback
from langchain.agents.middleware import before_model
from langchain.tools import ToolRuntime, tool
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import ToolException
from langchain_mcp_adapters.client import MultiServerMCPClient
from pydantic import BaseModel, Field

from fiscal_doc_agent.extraction import DateMentions, extract
from fiscal_doc_agent.parsing import ROOT, load_pages

REFERENCE_DATE = "2024-01-01"
SKILLS_DIR = ROOT / "skills"
Arm = Literal["mcp", "skill"]

RULES = f"""Classify each date against the reference date {REFERENCE_DATE}:
- Ongoing: the date is the start or end of a period stated in its item (e.g. 'X to Y'), and
  that period is active on {REFERENCE_DATE} (starts on or before it, ends on or after it).
- Expired: otherwise, the date is before {REFERENCE_DATE}.
- Upcoming: otherwise, the date is after {REFERENCE_DATE}.

A single cut-off or effective date is classified by the date itself, even if the rule or
change it marks still applies; then say in the reasoning whether that effect is still in force
on {REFERENCE_DATE}. Use the document context given with each item."""

AGENT_PROMPT = f"""You normalise and classify dates from a fiscal document.
Call normalize_dates with the texts of all items, copied exactly. Then call submit_dates once
with one record per date it returned: original_text is the item's text exactly as given (an
item with two dates gets two records), normalized_date is that date.

{RULES}"""

Status = Literal["Expired", "Upcoming", "Ongoing"]


class DateRecord(BaseModel):
    """Part 2 output contract, one per normalised date."""

    original_text: str
    normalized_date: str = Field(description="YYYY-MM-DD, as returned by normalize_dates.")
    status: Status
    reasoning: str = Field(description="Why this status, comparing against the reference date.")


def succeeded(message, tool: str) -> bool:
    """True if `message` is a non-error result of `tool`."""
    return isinstance(message, ToolMessage) and message.name == tool and message.status != "error"


def returned_dates(messages) -> dict[str, list[str]]:
    """{text: dates} for every text passed to a successful normalize_dates call in a transcript."""
    texts = {c["id"]: c["args"]["texts"] for m in messages if isinstance(m, AIMessage)
             for c in m.tool_calls if c["name"] == "normalize_dates"}
    return {text: dates for m in messages
            if succeeded(m, "normalize_dates") and m.tool_call_id in texts
            for text, dates in zip(texts[m.tool_call_id], json.loads(m.text))}


def submit_tool(expected: list[str]):
    """`submit_dates` for items `expected`, validated against the transcript.

    Errors go back to the agent to fix in the same run."""

    @tool
    def submit_dates(records: list[DateRecord], runtime: ToolRuntime) -> str:
        """Submit the classified dates, one record per date normalize_dates returned. Call once, last."""
        records = [DateRecord.model_validate(r) for r in records]
        returned = returned_dates(runtime.state["messages"])
        problems = [f"unexpected record for {r.original_text!r}" for r in records
                    if r.original_text not in expected]
        for text in expected:
            submitted = sorted(r.normalized_date for r in records if r.original_text == text)
            if text not in returned:
                problems.append(f"call normalize_dates with {text!r} exactly as given")
            elif submitted != sorted(returned[text]):
                problems.append(f"records for {text!r} have dates {submitted}, but "
                                f"normalize_dates returned {returned[text]}")
        if problems:
            raise ToolException("submit failed: " + "; ".join(problems))
        return "submitted"

    submit_dates.handle_tool_error = True  # ToolException -> error ToolMessage, agent retries
    return submit_dates


@before_model(can_jump_to=["end"])
def stop_after_submit(state, runtime):
    """End the run after a successful submit_dates; no closing model turn needed."""
    if succeeded(state["messages"][-1], "submit_dates"):
        return {"jump_to": "end"}
    return None


def mcp_tools():
    client = MultiServerMCPClient(
        {"dates": {"command": sys.executable, "args": ["-m", "fiscal_doc_agent.mcp_server"],
                   "transport": "stdio"}}
    )
    return client.get_tools()


@cache
def disable_general_purpose_subagent(provider: str | None) -> None:
    """deepagents only disables its general-purpose subagent via a process-wide harness profile,
    keyed by the provider name deepagents itself derives (hence its private helper). Once each."""
    register_harness_profile(
        provider,
        HarnessProfile(general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False)),
    )


@cache
def skill_tool():
    """normalize_dates from the skill's own folder (skills/normalize-dates/scripts/)."""
    path = SKILLS_DIR / "normalize-dates" / "scripts" / "normalize_dates.py"
    spec = importlib.util.spec_from_file_location("normalize_dates_skill", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return tool(module.normalize_dates)


async def build_agent(arm: Arm, model, submit):
    """deepagents harness trimmed to ls/read_file, with no general-purpose subagent. The arms
    differ only in how normalize_dates is delivered: an MCP tool bound from turn one, or a
    skill (the MCP arm's filesystem is the empty default, the skill arm's holds the skills)."""
    if arm == "mcp":
        tools, backend, extra = [*await mcp_tools()], None, []
    else:
        # skills/ served read-only at '/'; normalize_dates is bound only once the agent has read
        # a SKILL.md listing it in metadata.include_tools. create_deep_agent's plain `skills=`
        # can't supply tools, hence the explicit SkillsMiddleware.
        tools, backend = [], FilesystemBackend(root_dir=SKILLS_DIR, virtual_mode=True)
        extra = [SkillsMiddleware(backend=backend, sources=["/"], tools=[skill_tool()])]
    disable_general_purpose_subagent(get_model_provider(model))
    return create_deep_agent(
        model, [*tools, submit], system_prompt=AGENT_PROMPT,
        middleware=[FilesystemMiddleware(backend=backend, tools=["ls", "read_file"]),
                    stop_after_submit, *extra],
    )


async def run_part2(arm: Arm, model) -> dict:
    """Return {records, mentions, usage: {stage: usage_by_model}}; usage stages extract, agent."""
    if arm not in ("mcp", "skill"):  # before the paid extraction call
        raise ValueError(f"unknown arm {arm!r}")
    usage = {}

    with get_usage_metadata_callback() as cb:
        mentions = extract(load_pages(), DateMentions, model)
    usage["extract"] = cb.usage_metadata
    items = [{"original_text": m.text, "context": m.evidence.quote}
             for m in (mentions.distribution_date, mentions.estate_duty_date)]
    records, usage["agent"] = await classify_dates(items, model, arm)
    return {"records": records, "mentions": mentions.model_dump(), "usage": usage}


async def classify_dates(items: list[dict], model, arm: Arm) -> tuple[list[dict], dict]:
    """Agent normalises (via `arm`'s normalize_dates) and classifies [{original_text, context}]
    -> (records, usage)."""
    agent = await build_agent(arm, model, submit_tool([i["original_text"] for i in items]))
    with get_usage_metadata_callback() as cb:
        state = await agent.ainvoke({"messages": [("human", json.dumps(items, indent=2))]})
    return submitted_records(state["messages"]), cb.usage_metadata


def submitted_records(messages) -> list[dict]:
    """Records from the successful submit_dates call; raises if the agent never submitted."""
    ok = {m.tool_call_id for m in messages if succeeded(m, "submit_dates")}
    for m in messages:
        for c in getattr(m, "tool_calls", None) or []:
            if c["id"] in ok:
                return [DateRecord.model_validate(r).model_dump() for r in c["args"]["records"]]
    raise RuntimeError("agent finished without a successful submit_dates")
