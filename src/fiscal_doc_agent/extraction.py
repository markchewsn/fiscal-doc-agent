"""Whole-document structured extraction with page + quote evidence."""

from typing import Literal

from pydantic import BaseModel, Field, computed_field

SYSTEM_PROMPT = """You extract structured fields from a Singapore Ministry of Finance fiscal document.
The document is given page by page inside <page n="..."> markers.
Follow each field description exactly: it says which column, financial year and unit to use.
Every field needs evidence: the page number from the <page n="..."> marker and a quote copied
verbatim from that page (a sentence, or a table row as it appears) that supports the value.
Report numbers exactly as printed with their stated unit; never convert or estimate."""


class Evidence(BaseModel):
    page: int = Field(description="Page number from the <page n> marker the quote is on.")
    quote: str = Field(description="Text copied verbatim from that page supporting the value.")


class FloatField(BaseModel):
    value: float
    evidence: list[Evidence] = Field(description="At least one supporting quote.")


class MoneyField(BaseModel):
    """Amount as printed in the document; conversion to $billion is done in code."""

    value: float = Field(description="The number exactly as printed, without commas.")
    unit: Literal["$billion", "$million"] = Field(description="Unit the document states for it.")
    evidence: list[Evidence] = Field(description="At least one supporting quote.")

    @computed_field
    @property
    def billion(self) -> float:
        return round(self.value / 1000, 6) if self.unit == "$million" else self.value


class ListField(BaseModel):
    value: list[str]
    evidence: list[Evidence] = Field(description="Quotes covering every listed item.")


class Part1Fields(BaseModel):
    """The five Part 1 fields of the Source Document."""

    corporate_income_tax_fy2024: MoneyField = Field(
        description="Corporate Income Tax revenue for FY2024. '2024' means "
        "Financial Year 2024, whose only figures are the Estimated FY2024 column; do not use "
        "Revised FY2023 or Actual figures. Take it from the 'Budget for FY2024' summary table "
        "(in $billion), not from the $million annex tables."
    )
    corporate_income_tax_yoy_pct: FloatField = Field(
        description="Year-on-year percentage change in Corporate Income Tax, Estimated FY2024 "
        "versus Revised FY2023, as a signed percentage (negative for a decrease), e.g. -3.5. "
        "The document shows negative figures in parentheses: (3.5) means -3.5."
    )
    total_top_ups_fy2024: MoneyField = Field(
        description="Total Top-ups to Endowment and Trust Funds in FY2024. Use the most precise "
        "total the document gives: a $million table total beats a rounded $billion one."
    )
    operating_revenue_taxes: ListField = Field(
        description="Every tax mentioned in section 1.2 'Operating Revenue' (part of the FY2023 "
        "update; not section 2.2 of the same name), including each "
        "named component of 'Other Taxes'. Only taxes, levies and duties: exclude non-tax "
        "revenue such as fees, charges, premiums, contributions and NIRC. Use the document's "
        "names, deduplicated, in order of first appearance."
    )
    latest_actual_fiscal_position: MoneyField = Field(
        description="Overall Fiscal Position for the latest Actual (audited) financial year; "
        "this is the most recent column labelled Actual (FY2022), not Revised FY2023 "
        "or Estimated FY2024. Use the Overall Fiscal Position line, not the earlier Overall "
        "Budget Surplus/Deficit line. Negative for a deficit (shown in parentheses). Take it from "
        "the 'Fiscal Position in FY2022 and FY2023' table (in $billion), not from the $million "
        "annex tables."
    )


def render(pages: list[dict]) -> str:
    return "\n\n".join(f'<page n="{p["page"]}">\n{p["markdown"]}\n</page>' for p in pages)


def extract[T: BaseModel](pages: list[dict], schema: type[T], model) -> T:
    """One LLM call over the whole document, returning a validated `schema` instance."""
    structured = model.with_structured_output(schema, method="json_schema")
    return structured.invoke([("system", SYSTEM_PROMPT), ("human", render(pages))])


class DateMention(BaseModel):
    text: str = Field(description="The date phrase copied verbatim from the page.")
    evidence: Evidence


class DateMentions(BaseModel):
    """The two Part 2 date mentions of the Source Document."""

    distribution_date: DateMention = Field(
        description="The date the document was distributed, as the full phrase stating it "
        "(e.g. 'Distributed on ...: <date>')."
    )
    estate_duty_date: DateMention = Field(
        description="The date after which Estate Duty no longer applies, as the date alone "
        "(e.g. '1 January 2000')."
    )
