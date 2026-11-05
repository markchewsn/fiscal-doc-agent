"""Part 3: answer the demo queries with a multi-agent graph (Revenue + Expenditure Agents).

Usage: python scripts/part3_agents.py [--graph supervisor|swarm] [--yes]
Writes outputs/part3_<graph>.json + .md (per-query trace and usage summary).
Model is chosen by LLM_MODEL (default Bedrock Sonnet 5.5); see .env.example.
"""

import argparse
import json
from pathlib import Path

from fiscal_doc_agent.llm import PRICES_AS_OF, PRICES_SOURCE, cost_usd, get_model
from fiscal_doc_agent.parsing import ROOT
from fiscal_doc_agent.part3 import GRAPHS, RECURSION_LIMIT, run_graph

MAIN_QUERY = ("What are the key government revenue streams, and how will the Budget for the "
              "Future Energy Fund be supported?")
QUERIES = [
    MAIN_QUERY,  # cross-agent: the assignment query
    "Which revenue streams grow fastest in FY2024?",  # revenue only
    "What is the total of FY2024 fund Top-ups and which is largest?",  # expenditure only
    "Does the FY2024 GST revenue increase cover the GST Voucher Fund Top-up?",  # cross-agent
]
AGENT_RUNS = [2, 1, 1, 2]  # expected agent runs per query
AGENT_TURNS = 4  # ~search, read, read, answer (or handoff)
# Central LLM calls per query: supervisor routes once per agent run, then FINISH + synthesis;
# swarm makes one entry call.
PLANS = {
    "supervisor": (lambda runs: runs * (AGENT_TURNS + 1) + 2,
                   "one supervisor route per agent run, a FINISH route and a synthesis call"),
    "swarm": (lambda runs: runs * AGENT_TURNS + 1,
              "one entry call picking the first agent; agents hand off directly"),
}


def totals(usage: dict) -> tuple[int, int]:
    return (sum(u["input_tokens"] for u in usage.values()),
            sum(u["output_tokens"] for u in usage.values()))


def summary_row(run: dict) -> str:
    if "error" in run:
        return f"| {run['query']} | failed: {run['error']} | | | | |"
    tin, tout = totals(run["usage"])
    cost = "n/a" if run["cost_usd"] is None else f"{run['cost_usd']:.4f}"
    return (f"| {run['query']} | {run['llm_calls']} | {tin:,} | {tout:,} | {cost} | "
            f"{run['latency_s']} |")


def render_event(e: dict) -> list[str]:
    if e["type"] == "route":
        return [f"- **supervisor -> {e['next']}**: {e['reason']}"]
    if e["type"] == "entry":
        return [f"- **entry -> {e['next']}**: {e['reason']}"]
    if e["type"] == "handoff":
        return [f"- **{e['agent']} -> {e['next']}** (direct handoff): {e['reason']}",
                f"  - `{e['agent']}` hands over its findings:", "",
                *(f"    > {line}" for line in e["findings"].splitlines()), ""]
    if e["type"] == "final_answer" and "agent" in e:
        return [f"  - `{e['agent']}` writes the final answer (below)"]
    if e["type"] == "tool_call":
        args = ", ".join(f"{k}={v!r}" for k, v in e["args"].items())
        result = " ".join(e["result"].split())
        return [f"  - `{e['agent']}` calls `{e['tool']}({args})` -> `{result[:160]}...`"]
    if e["type"] == "agent_answer":
        return [f"  - `{e['agent']}` answers:", "",
                *(f"    > {line}" for line in e["text"].splitlines()), ""]
    return []  # the supervisor's final_answer is rendered on its own


def to_markdown(out: dict) -> str:
    header = ["| Query | LLM calls | Input tokens | Output tokens | Cost (USD) | Latency (s) |",
              "|---|---|---|---|---|---|"]
    lines = [f"# Part 3: {out['graph']} graph", "", f"Model: `{out['model']}`", "",
             "## Summary", "", *header, *map(summary_row, out["runs"]), "",
             f"Prices {out['prices']['as_of']}, {out['prices']['source']}", ""]
    for i, run in enumerate(out["runs"], 1):
        lines += [f"## Query {i}: {run['query']}", ""]
        if "error" in run:
            lines += [f"Failed: `{run['error']}`", ""]
            continue
        lines += ["### Trace", ""]
        for e in run["trace"]:
            lines += render_event(e)
        lines += ["", "### Final answer", "", run["answer"], ""]
    return "\n".join(lines) + "\n"


def main(kind="supervisor"):
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph", choices=sorted(GRAPHS), default=kind)
    ap.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    args = ap.parse_args()
    out_path = ROOT / "outputs" / f"part3_{args.graph}.json"

    model = get_model()
    model_id = getattr(model, "model_id", None) or getattr(model, "model", str(model))
    per_query, central = PLANS[args.graph]
    calls = sum(map(per_query, AGENT_RUNS))
    print(f"Plan: {len(QUERIES)} queries through the {args.graph} graph on {model_id}, "
          f"~{calls} LLM calls total (per query: ~{AGENT_TURNS} turns per agent run, {central}; "
          f"expected agent runs per query {AGENT_RUNS}). Hard cap {RECURSION_LIMIT} graph steps "
          "per query.")
    if not args.yes and input("Proceed? [y/N] ").strip().lower() != "y":
        return None

    out = {"graph": args.graph, "model": model_id, "runs": [],
           "prices": {"source": PRICES_SOURCE, "as_of": PRICES_AS_OF}}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    for q in QUERIES:
        try:
            run = {"query": q, **run_graph(args.graph, q, model)}
            run["cost_usd"] = cost_usd(run["usage"])
        except Exception as e:  # keep the paid runs of other queries; failure is recorded
            run = {"query": q, "error": f"{type(e).__name__}: {e}"}
        out["runs"].append(run)
        print(f"{summary_row(run)}\n")
        # Written after every query so a later failure never loses paid results.
        out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
        out_path.with_suffix(".md").write_text(to_markdown(out))
    print(f"Wrote {out_path} and .md")
    return out


if __name__ == "__main__":
    main()
