import json
import re

from langchain_core.runnables import RunnableLambda

from fiscal_doc_agent.extraction import MoneyField, Part1Fields, extract
from fiscal_doc_agent.llm import cost_usd
from fiscal_doc_agent.parsing import ROOT, SOURCE_PDF, load_pages


def test_parser_yields_37_pages_with_table_2_4_intact(tmp_path):
    pages = load_pages(SOURCE_PDF, cache_dir=tmp_path)
    assert [p["page"] for p in pages] == list(range(1, 38))
    p20 = pages[19]["markdown"]
    assert "|Goods and Services Tax Voucher Fund|6,000|" in p20
    assert "|Legal Aid Fund|2|" in p20
    assert "|**Total**|**20,352**|" in p20
    assert load_pages(SOURCE_PDF, cache_dir=tmp_path) == pages  # served from cache
    assert list(tmp_path.iterdir())


def test_cost_from_usage_splits_cached_input():
    usage = {
        "global.anthropic.claude-sonnet-5-5": {
            "input_tokens": 1_500_000,  # includes cache read + write
            "output_tokens": 100_000,
            "input_token_details": {"cache_read": 400_000, "cache_creation": 100_000},
        }
    }
    # 1M uncached * $2 + 0.1M out * $10 + 0.4M read * $0.10 + 0.1M write * $2.50
    assert round(cost_usd(usage), 6) == 2.0 + 1.0 + 0.04 + 0.25
    assert cost_usd({"gpt-x": {"input_tokens": 1, "output_tokens": 1}}) is None


def _field(value, page=1, **extra):
    return {"value": value, "evidence": [{"page": page, "quote": "q"}], **extra}


def test_money_converted_to_billion_in_code_not_by_model():
    assert MoneyField(**_field(20352, unit="$million")).billion == 20.352
    assert MoneyField(**_field(1.72, unit="$billion")).billion == 1.72
    assert "billion" not in MoneyField.model_json_schema()["properties"]  # not asked of model


class FakeStructuredModel:
    """Stands in for a chat model: records the prompt, returns a canned schema payload."""

    def __init__(self, payload):
        self.payload, self.prompts = payload, []

    def with_structured_output(self, schema, **_):
        def respond(messages):
            self.prompts.append(messages)
            return schema.model_validate(self.payload)

        return RunnableLambda(respond)


def test_extract_sends_whole_document_with_page_markers():
    payload = {name: _field(1.0, unit="$billion") for name in Part1Fields.model_fields}
    payload["operating_revenue_taxes"] = _field(["Corporate Income Tax"])
    model = FakeStructuredModel(payload)
    pages = [{"page": 1, "markdown": "alpha"}, {"page": 2, "markdown": "beta"}]

    result = extract(pages, Part1Fields, model)

    assert isinstance(result, Part1Fields)
    assert result.operating_revenue_taxes.value == ["Corporate Income Tax"]
    (messages,) = model.prompts
    human = messages[-1][1]
    assert '<page n="1">\nalpha' in human and '<page n="2">\nbeta' in human


def test_committed_part1_output():
    out = json.loads((ROOT / "outputs" / "part1_extraction.json").read_text())
    f = out["fields"]
    assert f["corporate_income_tax_fy2024"]["billion"] == 28.03
    assert f["corporate_income_tax_yoy_pct"]["value"] == -1.2
    assert f["total_top_ups_fy2024"]["billion"] == 20.352
    assert f["latest_actual_fiscal_position"]["billion"] == 1.72

    taxes = " | ".join(f["operating_revenue_taxes"]["value"]).casefold()
    expected = [  # taxes named in section 1.2
        "corporate income tax", "personal income tax", "goods and services tax",
        "assets taxes", "betting taxes", "foreign worker levy", "water conservation tax",
        "land betterment charge", "annual tonnage tax", "casino taxes",
    ]
    assert [t for t in expected if t not in taxes] == []
    assert "vehicle quota premiums" not in taxes  # a premium, not a tax
    assert "property tax" not in taxes  # only in section 2.2

    pages = {k: {e["page"] for e in v["evidence"]} for k, v in f.items()}
    assert 16 in pages["corporate_income_tax_fy2024"]
    assert 20 in pages["total_top_ups_fy2024"]
    assert 8 in pages["latest_actual_fiscal_position"]

    # Quotes must appear on the cited page, ignoring whitespace and Markdown table/bold markup.
    norm = lambda s: re.sub(r"[\s*|_]+", " ", s).strip()
    page_text = {p["page"]: norm(p["markdown"]) for p in load_pages()}
    for name, field in f.items():
        assert field["evidence"], name
        for ev in field["evidence"]:
            assert ev["quote"].strip() and norm(ev["quote"]) in page_text[ev["page"]], (name, ev)
    assert out["usage"] and out["cost_usd"] > 0


def test_cost_counts_bedrock_cache_writes_reported_by_ttl():
    # langchain-aws reports Bedrock cache writes per TTL and leaves cache_creation at 0
    usage = {
        "global.anthropic.claude-sonnet-5-5": {
            "input_tokens": 1_600_000,
            "output_tokens": 0,
            "input_token_details": {"cache_read": 400_000, "cache_creation": 0,
                                    "ephemeral_5m_input_tokens": 100_000,
                                    "ephemeral_1h_input_tokens": 100_000},
        }
    }
    # 1M uncached * $2 + 0.4M read * $0.10 + 0.1M 5m write * $2.50 + 0.1M 1h write * $4 (2x input)
    assert round(cost_usd(usage), 6) == 2.0 + 0.04 + 0.25 + 0.4
