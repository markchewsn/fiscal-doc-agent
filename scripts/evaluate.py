"""Compare the saved results in outputs/ with the expected answers in evals/golden.json,
which were checked by hand against the Source Document.

Usage: python scripts/evaluate.py [--label "what changed"] [-v]
Makes no LLM calls. To score a change, rerun the scripts that write outputs/ first.
Prints how many checks passed for each part and adds one line to evals/history.jsonl.
Only the assignment's own fields, dates and query are scored; the extra example dates and
Part 3 queries are not.
"""

import argparse
import json
import re
import time

from fiscal_doc_agent.parsing import ROOT

EVALS = ROOT / "evals"
OUTPUTS = ROOT / "outputs"
# suite -> (output file, golden key)
SUITES = {
    "part1": ("part1_extraction.json", "part1"),
    "part2_mcp": ("part2_mcp.json", "part2"),
    "part2_skill": ("part2_skill.json", "part2"),
    "part3_supervisor": ("part3_supervisor.json", "part3"),
    "part3_swarm": ("part3_swarm.json", "part3"),
}


def score_part1(gold: dict, out: dict) -> dict[str, bool]:
    fields, checks = out["fields"], {}
    for name, want in gold["numbers"].items():
        got = fields[name]
        if "billion" in want:
            checks[f"{name} value"] = got.get("billion") == want["billion"]
        else:
            checks[f"{name} value"] = got["value"] == want["value"]
        if "page" in want:
            checks[f"{name} page"] = want["page"] in {e["page"] for e in got["evidence"]}
    taxes = " | ".join(fields["operating_revenue_taxes"]["value"]).casefold()
    for tax in gold["operating_revenue_taxes"]["must_include"]:
        checks[f"tax includes {tax}"] = tax in taxes
    for tax in gold["operating_revenue_taxes"]["must_exclude"]:
        checks[f"tax excludes {tax}"] = tax not in taxes
    return checks


def score_part2(gold: dict, out: dict) -> dict[str, bool]:
    got = {r["normalized_date"]: r["status"] for r in out["records"]}
    checks = {f"{date} is {status}": got.get(date) == status for date, status in gold.items()}
    checks |= {f"no extra date {date}": False for date in sorted(set(got) - set(gold))}
    return checks


def score_part3(gold: dict, out: dict) -> dict[str, bool]:
    answers = [r.get("answer", "") for r in out["runs"] if r["query"] == gold["query"]]
    if not answers:  # a renamed query would otherwise score as missing every fact
        raise ValueError(f"no run for the query in evals/golden.json: {gold['query']!r}")
    answer = answers[0]
    return {f"mentions /{p}/": bool(re.search(p, answer)) for p in gold["must_mention"]}


SCORERS = {"part1": score_part1, "part2": score_part2, "part3": score_part3}


def score(golden: dict, outputs: dict[str, dict]) -> dict[str, dict[str, bool]]:
    """{suite: {check: passed}} for each suite whose output file is present."""
    return {suite: SCORERS[key](golden[key], outputs[file])
            for suite, (file, key) in SUITES.items() if file in outputs}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="", help="what changed since the last Eval Run; saves the scores to evals/history.jsonl")
    ap.add_argument("-v", action="store_true", help="list failed checks")
    args = ap.parse_args()

    golden = json.loads((EVALS / "golden.json").read_text())
    outputs = {p.name: json.loads(p.read_text()) for p in OUTPUTS.glob("*.json")}
    results = score(golden, outputs)

    run = {"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "label": args.label, "scores": {}}
    for suite, checks in results.items():
        passed, model = sum(checks.values()), outputs[SUITES[suite][0]].get("model", "?")
        run["scores"][suite] = {"passed": passed, "total": len(checks), "model": model}
        print(f"{suite:17} {passed:3}/{len(checks):<3} {passed / len(checks):6.1%}  {model}")
        for name, ok in checks.items():
            if args.v and not ok:
                print(f"    FAIL {name}")
    if args.label:
        with (EVALS / "history.jsonl").open("a") as history:
            history.write(json.dumps(run) + "\n")


if __name__ == "__main__":
    main()
