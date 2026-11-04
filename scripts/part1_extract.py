"""Part 1: extract the five fields from the Source Document with one LLM call.

Usage: python scripts/part1_extract.py [--yes] [--out outputs/part1_extraction.json]
Model is chosen by LLM_MODEL (default Bedrock Sonnet 5.5); see .env.example.
"""

import argparse
import json
import time
from pathlib import Path

from langchain_core.callbacks import get_usage_metadata_callback

from fiscal_doc_agent.extraction import Part1Fields, extract, render
from fiscal_doc_agent.llm import PRICES_AS_OF, PRICES_SOURCE, cost_usd, get_model
from fiscal_doc_agent.parsing import ROOT, load_pages


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    ap.add_argument("--out", type=Path, default=ROOT / "outputs" / "part1_extraction.json")
    args = ap.parse_args()

    pages = load_pages()
    model = get_model()
    model_id = getattr(model, "model_id", None) or getattr(model, "model", str(model))
    print(f"Plan: 1 LLM call to {model_id}, {len(pages)} pages, {len(render(pages)):,} chars of input.")
    if not args.yes and input("Proceed? [y/N] ").strip().lower() != "y":
        return

    start = time.perf_counter()
    with get_usage_metadata_callback() as cb:
        fields = extract(pages, Part1Fields, model)
    latency = time.perf_counter() - start

    result = {
        "model": model_id,
        "fields": fields.model_dump(),
        "usage": cb.usage_metadata,
        "cost_usd": cost_usd(cb.usage_metadata),
        "prices": {"source": PRICES_SOURCE, "as_of": PRICES_AS_OF},
        "latency_s": round(latency, 2),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: v.get("billion", v["value"]) for k, v in result["fields"].items()}, indent=2))
    print(f"Usage: {cb.usage_metadata}\nCost: ${result['cost_usd']}  Latency: {latency:.1f}s\nWrote {args.out}")


if __name__ == "__main__":
    main()
