"""Part 3 (Swarm): same queries, agents, prompts and tools as part3_agents.py, through the
Swarm graph. Then compares it with the committed Supervisor output.

Usage: python scripts/part3_compare.py [--yes]
Writes outputs/part3_swarm.json + .md and outputs/part3_comparison.md.
Run scripts/part3_agents.py first (its Supervisor output is committed).
"""

import json

from part3_agents import main, totals

from fiscal_doc_agent.parsing import ROOT

OUTPUTS = ROOT / "outputs"
KINDS = ("supervisor", "swarm")


def path(run: dict) -> str:
    """Agents in the order they were sent to."""
    hops = [e["next"] for e in run["trace"] if e["type"] in ("route", "entry", "handoff")]
    return " > ".join(h.removesuffix("_agent") for h in hops if h != "FINISH")


def row(label: str, run: dict) -> str:
    if "error" in run:
        return f"| {label} | failed: {run['error']} | | | | | |"
    tin, tout = totals(run["usage"])
    return (f"| {label} | {path(run)} | {run['llm_calls']} | {tin:,} | {tout:,} | "
            f"{run['cost_usd']:.4f} | {run['latency_s']} |")


def total_row(graph: str, runs: list[dict]) -> str:
    ok = [r for r in runs if "error" not in r]
    tin, tout = map(sum, zip(*(totals(r["usage"]) for r in ok)))
    return (f"| **Total {graph}** | | {sum(r['llm_calls'] for r in ok)} | {tin:,} | {tout:,} | "
            f"{sum(r['cost_usd'] for r in ok):.4f} | "
            f"{round(sum(r['latency_s'] for r in ok), 2)} |")


def comparison(outs: dict) -> str:
    lines = [
        "# Part 3: Supervisor vs Swarm", "",
        f"Model: `{outs['swarm']['model']}`. Both graphs use the same two agents (same "
        "system prompts and document tools); only the topology differs. The swarm also gives "
        "each agent a `transfer_to_<peer>` tool and tells it when to hand off. In the "
        "supervisor, the supervisor tells each agent what to find. Supervisor: a central LLM "
        "router picks every hop and a final synthesis call writes the answer. Swarm: one "
        "entry call picks the first agent, agents hand off directly via "
        "`transfer_to_<peer>` tools, and the last active agent writes the answer.", "",
        "| Query / graph | Agent path | LLM calls | Input tokens | Output tokens | Cost (USD) "
        "| Latency (s) |",
        "|---|---|---|---|---|---|---|",
    ]
    for i, query in enumerate(r["query"] for r in outs["swarm"]["runs"]):
        lines.append(f"| **Q{i + 1}**: {query} | | | | | | |")
        lines += [row(g, outs[g]["runs"][i]) for g in KINDS]
    lines += [total_row(g, outs[g]["runs"]) for g in KINDS]
    lines += [
        "", "## Where the difference comes from", "",
        "- **Central calls:** per query the supervisor makes one routing call per agent run, "
        "a FINISH routing call and a synthesis call; each re-sends the question and every "
        "agent's findings so far. The swarm makes one small entry call, then each agent passes "
        "the question straight to the next agent itself.",
        "- **Synthesis:** the supervisor's final answer is a separate call that re-reads all "
        "findings and rewrites them, roughly doubling output tokens. In the swarm the last "
        "agent writes the final answer in the turn it would have used to report back.",
        "- **Division of labour:** the supervisor decides which agent handles each part; "
        "swarm agents decide for themselves, and the document tools reach every page: in Q1 the "
        "revenue agent searched for the Future Energy Fund before handing off.", "",
        "Caveat: one run per graph. Agent turn counts vary between runs, so differences of a "
        "call or two per query are noise, but the supervisor's extra calls happen on every "
        "query.",
    ]
    lines += ["", f"Prices {outs['swarm']['prices']['as_of']}, "
              f"{outs['swarm']['prices']['source']}"]
    return "\n".join(lines) + "\n"


def compare():
    swarm = main("swarm")
    if swarm is None or swarm["graph"] != "swarm":
        return
    supervisor = json.loads((OUTPUTS / "part3_supervisor.json").read_text())
    outs = {"supervisor": supervisor, "swarm": swarm}
    (OUTPUTS / "part3_comparison.md").write_text(comparison(outs))
    print(f"Wrote {OUTPUTS / 'part3_comparison.md'}")


if __name__ == "__main__":
    compare()
