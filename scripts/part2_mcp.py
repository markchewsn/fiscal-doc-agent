"""Part 2 (MCP arm): extract two dates; an agent normalises them via a stdio MCP tool and
classifies them vs 2024-01-01.

Usage: python scripts/part2_mcp.py [--yes] [--out outputs/part2_mcp.json]
Model is chosen by LLM_MODEL (default Bedrock Sonnet 5.5); see .env.example.
"""

import argparse
import asyncio
import json
import time
from pathlib import Path

from fiscal_doc_agent.llm import PRICES_AS_OF, PRICES_SOURCE, cost_usd, get_model
from fiscal_doc_agent.parsing import ROOT
from fiscal_doc_agent.part2 import REFERENCE_DATE, classify_dates, run_part2

# Robustness demo: financial-year periods covering all three states against 2024-01-01:
# FY2022 Expired (ended 2023-03-31), FY2023 Ongoing (contains it), FY2024 Upcoming.
# Same agent and tool as the required dates; not part of the required output.
PERIODS = [
    {"original_text": f"Financial Year {fy}: 1 April {fy} to 31 March {fy + 1}",
     "context": "Robustness demo, not from the Source Document: a Singapore Government "
                "financial year."}
    for fy in (2022, 2023, 2024)
]


def to_markdown(result: dict) -> str:
    def table(records):
        rows = ["| Original text | Normalized | Status | Reasoning |", "|---|---|---|---|"]
        rows += [f"| {r['original_text']} | {r['normalized_date']} | **{r['status']}** | "
                 f"{r['reasoning']} |" for r in records]
        return rows

    lines = [
        f"# Part 2 dates ({result['arm']} arm)", "",
        f"Model: `{result['model']}`  ",
        f"Reference date: {result['reference_date']}  ",
        f"Latency: {result['latency_s']}s", "",
        *table(result["records"]), "",
        "## Evidence", "",
        *(f"- `{name}` p{m['evidence']['page']}: `{' '.join(m['evidence']['quote'].split())}`"
          for name, m in result["mentions"].items()), "",
        "## Token usage and cost", "",
        "| Stage | Input | Output | Cost (USD) |", "|---|---|---|---|",
    ]
    for stage, by_model in result["usage"].items():
        tin = sum(u["input_tokens"] for u in by_model.values())
        tout = sum(u["output_tokens"] for u in by_model.values())
        lines.append(f"| {stage} | {tin:,} | {tout:,} | {result['cost_usd'][stage]:.4f} |")
    lines += ["", f"Prices {result['prices']['as_of']}, {result['prices']['source']}", "",
              "## Robustness demo (periods, separate from the required output)", "",
              *table(result["robustness_demo"])]
    return "\n".join(lines) + "\n"


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    ap.add_argument("--out", type=Path, default=ROOT / "outputs" / "part2_mcp.json")
    args = ap.parse_args()

    model = get_model()
    model_id = getattr(model, "model_id", None) or getattr(model, "model", str(model))
    print(f"Plan: ~5 LLM calls to {model_id}: 1 date extraction (whole document), then ~2 "
          "agent turns (normalize_dates via MCP, then classify and submit_dates) for the "
          "document dates and ~2 more for the robustness-demo periods; +1 per rejected "
          "submit_dates the agent retries.")
    if not args.yes and input("Proceed? [y/N] ").strip().lower() != "y":
        return

    start = time.perf_counter()
    result = await run_part2("mcp", model)
    latency = time.perf_counter() - start
    demo, demo_usage = await classify_dates(PERIODS, model)
    usage = {**result["usage"], "robustness_demo": demo_usage}
    costs = {stage: cost_usd(u) for stage, u in usage.items()}

    out = {
        "arm": "mcp",
        "model": model_id,
        "reference_date": REFERENCE_DATE,
        "records": result["records"],
        "mentions": result["mentions"],
        "robustness_demo": demo,
        "usage": usage,
        "cost_usd": costs,
        "prices": {"source": PRICES_SOURCE, "as_of": PRICES_AS_OF},
        "latency_s": round(latency, 2),  # required pipeline only, excludes the demo
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    args.out.with_suffix(".md").write_text(to_markdown(out))
    print(json.dumps({"records": out["records"], "robustness_demo": demo}, indent=2))
    print(f"Cost: {costs}\nWrote {args.out} and .md")


if __name__ == "__main__":
    asyncio.run(main())
