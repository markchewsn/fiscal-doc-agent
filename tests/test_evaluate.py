import sys

import pytest

from fiscal_doc_agent.parsing import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
from evaluate import score  # noqa: E402

GOLDEN = {
    "part1": {
        "numbers": {"total_top_ups_fy2024": {"billion": 20.352, "page": 20},
                    "corporate_income_tax_yoy_pct": {"value": -1.2}},
        "operating_revenue_taxes": {"must_include": ["goods and services tax"],
                                    "must_exclude": ["property tax"]},
    },
    "part2": {"2024-02-16": "Upcoming", "2008-02-15": "Expired"},
    "part3": {"query": "Q?", "must_mention": [r"Future Energy Fund", r"\bGST\b"]},
}


def _field(value, *pages, **extra):
    return {"value": value, "evidence": [{"page": p, "quote": "q"} for p in pages], **extra}


def _record(date, status):
    return {"original_text": "t", "normalized_date": date, "status": status, "reasoning": "r"}


OUTPUTS = {
    "part1_extraction.json": {"fields": {
        "total_top_ups_fy2024": _field(20352.0, 19, unit="$million", billion=20.35),  # wrong value and page
        "corporate_income_tax_yoy_pct": _field(-1.2, 16),
        "operating_revenue_taxes": _field(["Goods and Services Tax", "Property Tax"], 5),
    }},
    "part2_mcp.json": {"records": [_record("2024-02-16", "Upcoming"), _record("2008-02-15", "Ongoing"),
                                   _record("1999-01-01", "Expired")]},  # wrong status, extra date
    "part3_swarm.json": {"runs": [{"query": "Q?", "answer": "The Future Energy Fund gets $5b."},
                                  {"query": "extra demo query", "answer": "GST"}]},  # demo not scored
}


def test_score_marks_each_wrong_answer_and_skips_missing_outputs():
    assert score(GOLDEN, OUTPUTS) == {
        "part1": {
            "total_top_ups_fy2024 value": False,
            "total_top_ups_fy2024 page": False,
            "corporate_income_tax_yoy_pct value": True,
            "tax includes goods and services tax": True,
            "tax excludes property tax": False,
        },
        "part2_mcp": {
            "2024-02-16 is Upcoming": True,
            "2008-02-15 is Expired": False,
            "no extra date 1999-01-01": False,
        },
        "part3_swarm": {
            "mentions /Future Energy Fund/": True,
            r"mentions /\bGST\b/": False,
        },
    }


def test_score_refuses_outputs_without_the_golden_query():
    with pytest.raises(ValueError, match="no run for the query"):
        score(GOLDEN, {"part3_swarm.json": {"runs": [{"query": "renamed query", "answer": "GST"}]}})
