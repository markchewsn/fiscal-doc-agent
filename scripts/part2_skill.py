"""Part 2 (Skill arm): same pipeline as part2_mcp.py, but normalize_dates is delivered as an
Agent Skill (bound only after the agent reads its SKILL.md). Then compares token usage and
cost with the committed MCP arm output.

Usage: python scripts/part2_skill.py [--yes] [--out outputs/part2_skill.json]
Writes outputs/part2_skill.json + .md and outputs/part2_comparison.md.
Run scripts/part2_mcp.py first (its output is committed).
"""

import asyncio
import json

from part2_mcp import main

from fiscal_doc_agent.parsing import ROOT

OUTPUTS = ROOT / "outputs"


def tokens(by_model: dict, key: str) -> int:
    return sum(u[key] for u in by_model.values())


def statuses(result: dict) -> dict:
    return {r["normalized_date"]: r["status"] for r in result["records"] + result["robustness_demo"]}


def comparison(mcp: dict, skill: dict) -> str:
    lines = [
        "# Part 2: MCP vs Skill tool delivery", "",
        f"Model: `{skill['model']}`. Same deepagents harness, prompt and `normalize_dates` "
        "function (same name, schema and description) in both arms; only the delivery differs. "
        "MCP: bound from the first agent turn via a local stdio MCP server. Skill: listed by "
        "name and description in the system prompt, bound only after the agent reads "
        "`skills/normalize-dates/SKILL.md`.", "",
        "| Stage | MCP input | Skill input | MCP output | Skill output | MCP USD | Skill USD |",
        "|---|---|---|---|---|---|---|",
    ]
    for stage in skill["usage"]:
        m, s = mcp["usage"][stage], skill["usage"][stage]
        lines.append(
            f"| {stage} | {tokens(m, 'input_tokens'):,} | {tokens(s, 'input_tokens'):,} | "
            f"{tokens(m, 'output_tokens'):,} | {tokens(s, 'output_tokens'):,} | "
            f"{mcp['cost_usd'][stage]:.4f} | {skill['cost_usd'][stage]:.4f} |")
    agree = statuses(mcp) == statuses(skill)
    lines += [
        "", "`extract` is identical in both arms (no tools); `agent` and `robustness_demo` "
        "are where tool delivery matters.", "",
        f"Latency (extraction + agent on the two document dates): MCP {mcp['latency_s']}s, "
        f"Skill {skill['latency_s']}s.", "",
        f"Date statuses agree across arms: **{'yes' if agree else 'NO'}**", "",
        "## Why the Skill arm uses more tokens", "",
        "Progressive disclosure defers a tool's schema until the skill is read. That pays off "
        "only when the deferred schemas are bigger than the fixed cost of the skill mechanism. "
        "Here the skill is always needed, and it defers one small tool, so the fixed cost "
        "dominates:", "",
        "- **Deferred:** only the `normalize_dates` schema, a short tool definition, and "
        "only on the first agent turn.",
        "- **Added every turn:** the skills section deepagents appends to the system prompt "
        "(the skill list plus generic instructions on how to use skills), which is several "
        "times longer than that schema.",
        "- **Added turn:** the agent must call `read_file` on SKILL.md before it can "
        "normalise, so a run takes one more model call. Each call re-sends the whole "
        "context, and the SKILL.md body stays in history for later turns. The extra "
        "`read_file` call is also why output tokens are higher.",
        "- **Cache:** on Bedrock, deepagents can't add a tool mid-conversation, so the tool "
        "list changes after the read and the cached prompt prefix is rebuilt (more cache "
        "writes). Native Anthropic and OpenAI models add it without breaking the cache.", "",
        "Skills should win when an agent has many tools, or tools it seldom needs: the MCP arm "
        "pays for every schema on every turn, while the skills section grows by one line per "
        "skill.", "",
        "Caveat: one run per arm. USD includes prompt-cache reads and writes, whose split "
        "depends on cache state, so the token columns are the cleaner comparison.", "",
        f"Prices {skill['prices']['as_of']}, {skill['prices']['source']}",
    ]
    return "\n".join(lines) + "\n"


async def compare():
    skill = await main("skill")
    if skill is None:
        return
    mcp = json.loads((OUTPUTS / "part2_mcp.json").read_text())
    (OUTPUTS / "part2_comparison.md").write_text(comparison(mcp, skill))
    print(f"Wrote {OUTPUTS / 'part2_comparison.md'}")


if __name__ == "__main__":
    asyncio.run(compare())
