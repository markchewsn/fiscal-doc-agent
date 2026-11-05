# Part 3: swarm graph

Model: `global.anthropic.claude-sonnet-5-5`

## Summary

| Query | LLM calls | Input tokens | Output tokens | Cost (USD) | Latency (s) |
|---|---|---|---|---|---|
| What are the key government revenue streams, and how will the Budget for the Future Energy Fund be supported? | 7 | 19,648 | 2,612 | 0.0654 | 22.71 |
| Which revenue streams grow fastest in FY2024? | 4 | 7,984 | 1,285 | 0.0288 | 12.23 |
| What is the total of FY2024 fund Top-ups and which is largest? | 5 | 8,595 | 578 | 0.0230 | 7.6 |
| Does the FY2024 GST revenue increase cover the GST Voucher Fund Top-up? | 8 | 26,038 | 1,441 | 0.0665 | 16.56 |

Prices 2026-10-06, https://platform.claude.com/docs/en/about-claude/pricing

## Query 1: What are the key government revenue streams, and how will the Budget for the Future Energy Fund be supported?

### Trace

- **entry -> revenue_agent**: The question opens with the key government revenue streams (Operating Revenue, tax and non-tax sources), which is the revenue_agent's domain, so it should start. The Future Energy Fund part concerns a top-up to an endowment or trust fund and what it funds, which the expenditure_agent can cover afterwards.
  - `revenue_agent` calls `search_document(query='Operating Revenue tax revenue streams', k=5)` -> `[{"page": 9, "score": 2.19, "snippet": "###### **Breakdown of Government Operating Revenue in FY2023**<sup>**1**</sup> ###### **Chart 1.1** <!-- Start of pictur...`
  - `revenue_agent` calls `search_document(query='Future Energy Fund', k=3)` -> `[{"page": 18, "score": 6.84, "snippet": " as an international financial centre. The Government will establish the Future Energy Fund with an initial injection o...`
  - `revenue_agent` calls `read_page(page=13)` -> `#### **02 Outlook for Financial Year 2024** ###### _2.1 Budget for FY2024_ A basic deficit of $6.1 billion (0.8% of GDP) is estimated for FY2024. After factorin...`
  - `revenue_agent` calls `read_page(page=18)` -> `###### _2.6 Special Transfers_ ###### <u>Special Transfers to Households ($2.6 billion)</u> In addition to transfers from the Government’s Operating Expenditure...`
  - `revenue_agent` calls `read_page(page=9)` -> `###### **Breakdown of Government Operating Revenue in FY2023**<sup>**1**</sup> ###### **Chart 1.1** <!-- Start of picture text --> Withholding Tax, 2.1% Statuto...`
- **revenue_agent -> expenditure_agent** (direct handoff): Confirm how the Future Energy Fund is supported in Budget 2024: the initial injection/top-up amount ($5.0b appears on p.16, 18, 20), what it funds, and the total Top-ups to Endowment and Trust Funds ($20.4b), with page citations. Then write the final combined answer covering both revenue streams and the Future Energy Fund.
  - `revenue_agent` hands over its findings:

    > Revenue side (MOF Analysis of Revenue and Expenditure FY2024): Estimated FY2024 Operating Revenue is $108.6b (15.1% of GDP), up $4.3b (4.2%) from Revised FY2023 $104.3b (p.13). Key streams in FY2023 as % of Total Revenue (p.9): Corporate Income Tax 27.2%, Personal Income Tax 16.8%, GST 15.7%, Other Taxes 8.4%, Assets Taxes 5.7%, Stamp Duty 5.7%, Vehicle Quota Premiums 4.5%, Fees and Charges (excl. VQP) 3.9%, Customs/Excise/Carbon Taxes 3.3%, Betting Taxes 3.0%, Motor Vehicle Taxes 2.5%, Withholding Tax 2.1%, Statutory Boards' Contributions 0.7%, Others 0.6%. Operating Revenue is 82.0% of Total Revenue in FY2023; NIRC is 18.0% (p.9). FY2024 changes (p.13): GST +$3.0b (18.5%) to $19.4b; Assets Taxes +$0.8b (12.8%) to $6.7b; Personal Income Tax +$0.5b (3.1%) to $18.1b; Motor Vehicle Taxes +$0.2b (9.3%) to $2.8b; Statutory Boards' Contributions -$0.4b (58.8%) to $0.3b. NIRC FY2024 is $23.5b (p.13).

  - `expenditure_agent` calls `search_document(query='Future Energy Fund top-up', k=6)` -> `[{"page": 18, "score": 9.55, "snippet": " as an international financial centre. The Government will establish the Future Energy Fund with an initial injection o...`
  - `expenditure_agent` calls `read_page(page=18)` -> `###### _2.6 Special Transfers_ ###### <u>Special Transfers to Households ($2.6 billion)</u> In addition to transfers from the Government’s Operating Expenditure...`
  - `expenditure_agent` calls `read_page(page=16)` -> `###### **Budget for FY2024** ###### **Table 2.1** |BLANK|**Revised**<br>**FY2023**|**Estimated**<br>**FY2024**|**Change O**<br>**Revised FY**|**ver**<br>**2023*...`
  - `expenditure_agent` calls `read_page(page=20)` -> `###### **Top-ups to Endowment and Trust Funds in FY2024** ###### **Table 2.4** ||**Estimated FY2024**<br>**($ million)**| |---|---| |Goods and Services Tax Vouc...`
  - `expenditure_agent` writes the final answer (below)

### Final answer

**Revenue streams**

- **Operating Revenue:** It is estimated at $108.6b in FY2024, which is 15.1% of GDP. That is up $4.3b (4.2%) from $104.3b in Revised FY2023 (p.13).
- **Main sources, as a share of Total Revenue in FY2023 (p.9):**
  - Corporate Income Tax: 27.2%
  - Personal Income Tax: 16.8%
  - GST: 15.7%
  - Other Taxes: 8.4%
  - Assets Taxes: 5.7%
  - Stamp Duty: 5.7%
  - Vehicle Quota Premiums: 4.5%
  - Fees and Charges (excluding Vehicle Quota Premiums): 3.9%
  - Customs, Excise and Carbon Taxes: 3.3%
  - Betting Taxes: 3.0%
  - Motor Vehicle Taxes: 2.5%
  - Withholding Tax: 2.1%
  - Statutory Boards' Contributions: 0.7%
  - Others: 0.6%
- **Operating Revenue versus NIRC:** Operating Revenue is 82.0% of Total Revenue in FY2023. The Net Investment Returns Contribution (NIRC) is the other 18.0% (p.9).
- **Main changes in FY2024 (pp.13, 16):**
  - GST rises $3.0b (18.5%) to $19.4b.
  - Assets Taxes rise $0.8b (12.8%) to $6.7b.
  - Personal Income Tax rises $0.5b (3.1%) to $18.1b.
  - Motor Vehicle Taxes rise $0.2b (9.3%) to $2.8b.
  - Statutory Boards' Contributions fall $0.4b (58.8%) to $0.3b.
  - Corporate Income Tax falls $0.35b (1.2%) to $28.0b.
- **NIRC:** It is $23.5b in FY2024 (pp.13, 16).

**Future Energy Fund**

- **How it is supported:** The Future Energy Fund is not funded from a revenue stream. It is supported by a one-off Special Transfer. In Budget 2024 the Government will establish the Fund with an initial injection of $5.0b, counted under Top-ups to Endowment and Trust Funds (p.18). The Fund had no top-up in FY2023 (p.16).
- **What it funds:** It will invest in critical infrastructure for the energy transition (p.18).
- **Place in the total:** The $5.0b is the second-largest top-up, after the GST Voucher Fund's $6.0b (p.20). Total Top-ups to Endowment and Trust Funds are $20.4b (Table 2.4 gives $20,352m). That is down from $24.3b in FY2023 (pp.16, 18, 20).
- **How the top-ups are paid for:** Top-ups are part of Special Transfers, which are $23.3b in FY2024 (p.16). The Budget shows them as a deduction in arriving at the overall budget position (p.16). They are therefore met from the Operating Revenue streams above, together with the $23.5b NIRC. The FY2024 overall budget deficit is $2.9b, and the overall fiscal position is a $0.78b surplus (p.16).

## Query 2: Which revenue streams grow fastest in FY2024?

### Trace

- **entry -> revenue_agent**: The question asks about which revenue streams grew fastest in FY2024, which concerns Operating Revenue, tax and non-tax revenue streams and their growth rates. This is the revenue agent's domain.
  - `revenue_agent` calls `search_document(query='operating revenue growth FY2024 tax revenue increase', k=8)` -> `[{"page": 13, "score": 10.23, "snippet": "Estimated FY2024 Operating Revenue is $108.6 billion (15.1% of GDP). This is an increase of $4.3 billion (4.2%) over t...`
  - `revenue_agent` calls `read_page(page=13)` -> `#### **02 Outlook for Financial Year 2024** ###### _2.1 Budget for FY2024_ A basic deficit of $6.1 billion (0.8% of GDP) is estimated for FY2024. After factorin...`
  - `revenue_agent` calls `read_page(page=26)` -> `###### **Table 3.2a: Revenue Collections for FY2018 to FY2024 ($ million)** |**B**<br>**B**|**LANK**<br>**FY2018**<br>**LANK**|**FY2019**|**FY2020**|**FY2021**|...`
  - `revenue_agent` writes the final answer (below)

### Final answer

**Goods and Services Tax (GST) grows fastest in FY2024, followed by Assets Taxes and then Motor Vehicle Taxes.** Total Operating Revenue is estimated at $108.6 billion in FY2024. That is up $4.3 billion (4.2%) from $104.3 billion in Revised FY2023 (p.13).

**Fastest-growing streams, Estimated FY2024 against Revised FY2023 (p.13):**
1. **GST:** up $3.0 billion (18.5%) to $19.4 billion. The increase comes from the higher GST rate and expected consumption growth.
2. **Assets Taxes:** up $0.8 billion (12.8%) to $6.7 billion. The drivers are higher Property Tax rates from 1 January 2024 and higher property Annual Values.
3. **Motor Vehicle Taxes:** up $0.2 billion (9.3%) to $2.8 billion, as COE quota supply is expected to recover further.
4. **Personal Income Tax:** up $0.5 billion (3.1%) to $18.1 billion. The drivers are nominal wage growth in 2023 and the higher top marginal tax rate from Year of Assessment 2024.

**Other streams, with growth calculated from Table 3.2a (p.26):**
- Withholding Tax is up about 5.5%, from $2,187 million to $2,307 million.
- Customs, Excise and Carbon Taxes are up about 4.9%, from $3,398 million to $3,564 million.
- Fees and Charges (excluding Vehicle Quota Premium) are up about 4.4%, from $4,067 million to $4,247 million.
- Betting Taxes are up about 3.4%, from $3,151 million to $3,257 million.
- Vehicle Quota Premium is up about 1.3%, from $4,664 million to $4,725 million.

**Declining streams (pp.13, 26):**
- Statutory Boards' Contributions fall 58.8%, from $748 million to $308 million, because of lower expected contributions from the Monetary Authority of Singapore.
- Corporate Income Tax falls about 1.2%, from $28,380 million to $28,029 million.
- Stamp Duty falls about 3.1%, from $5,917 million to $5,731 million.

GST is also the largest contributor to the dollar increase. The sources I read give percentage growth for only the four streams listed first. The percentages for the other streams are my own calculations from the table.

## Query 3: What is the total of FY2024 fund Top-ups and which is largest?

### Trace

- **entry -> expenditure_agent**: The question is about Top-ups to Endowment and Trust Funds in FY2024, including their total and which is largest. These are government spending items covered by the expenditure agent, not revenue streams.
  - `expenditure_agent` calls `search_document(query='Top-ups to Endowment and Trust Funds FY2024')` -> `[{"page": 11, "score": 9.81, "snippet": "|---| |**Special Transfers:**<br>**27,169**| |**Special Transfers Excluding Top-ups to Endowment and Trust Funds**| |Co...`
  - `expenditure_agent` calls `read_page(page=20)` -> `###### **Top-ups to Endowment and Trust Funds in FY2024** ###### **Table 2.4** ||**Estimated FY2024**<br>**($ million)**| |---|---| |Goods and Services Tax Vouc...`
  - `expenditure_agent` calls `sum_amounts(values=[6000, 5000, 2000, 2000, 2000, 1800, 1000, 500, 50, 2])` -> `20352.0...`
  - `expenditure_agent` writes the final answer (below)

### Final answer

The FY2024 Top-ups to Endowment and Trust Funds total **$20,352 million** (Estimated FY2024). The sum of the ten listed funds matches the table's stated total (p. 20, Table 2.4).

The **Goods and Services Tax Voucher Fund** is the largest, at **$6,000 million**. That is about 29% of the total. The Future Energy Fund is next at $5,000 million.

The other funds are:
- Edusave Endowment Fund: $2,000 million
- Financial Sector Development Fund: $2,000 million
- National Productivity Fund: $2,000 million
- National Research Fund: $1,800 million
- Progressive Wage Credit Scheme Fund: $1,000 million
- Skills Development Fund: $500 million
- Public Transport Fund: $50 million
- Legal Aid Fund: $2 million

## Query 4: Does the FY2024 GST revenue increase cover the GST Voucher Fund Top-up?

### Trace

- **entry -> revenue_agent**: The question starts from the FY2024 GST revenue increase, which is a tax revenue stream and falls under the revenue agent's scope. Its figure is needed first as the baseline. The expenditure agent can then supply the GST Voucher Fund top-up amount to compare against it.
  - `revenue_agent` calls `search_document(query='GST revenue increase FY2024')` -> `[{"page": 13, "score": 8.07, "snippet": "Estimated FY2024 Operating Revenue is $108.6 billion (15.1% of GDP). This is an increase of $4.3 billion (4.2%) over th...`
  - `revenue_agent` calls `search_document(query='Goods and Services Tax collections expected')` -> `[{"page": 13, "score": 8.84, "snippet": "$104.3 billion. The increase relative to Revised FY2023 is mainly due to higher collections expected from Goods and Ser...`
  - `revenue_agent` calls `read_page(page=13)` -> `#### **02 Outlook for Financial Year 2024** ###### _2.1 Budget for FY2024_ A basic deficit of $6.1 billion (0.8% of GDP) is estimated for FY2024. After factorin...`
  - `revenue_agent` calls `read_page(page=26)` -> `###### **Table 3.2a: Revenue Collections for FY2018 to FY2024 ($ million)** |**B**<br>**B**|**LANK**<br>**FY2018**<br>**LANK**|**FY2019**|**FY2020**|**FY2021**|...`
- **revenue_agent -> expenditure_agent** (direct handoff): Confirm the GST Voucher Fund Top-up amount for Estimated FY2024 (and the Revised FY2023 figure) in $ billion with page citation, state what it funds, and compare it with the GST revenue increase of $3.0b (18.5%) to say whether the increase covers the top-up. Write the final combined answer.
  - `revenue_agent` hands over its findings:

    > Revenue side: GST collections estimated to rise by $3.0 billion (18.5%) from Revised FY2023 $16.363b to Estimated FY2024 $19.394b (increase about $3.03b), due to the GST rate increase and expected consumption growth (p.13; Table 3.2a p.26). A search snippet from p.16 shows a Top-ups table row 'GST Voucher Fund | 2.40 | 6.00', but I have not confirmed which column is FY2024 (total top-ups to Endowment and Trust Funds in FY2024 are $20.4b per p.13).

  - `expenditure_agent` calls `search_document(query='GST Voucher Fund top-up')` -> `[{"page": 18, "score": 8.61, "snippet": " Trust Funds ($20.4 billion)</u> In Budget 2024, the Government will top up the GST Voucher Fund by $6.0 billion to mee...`
  - `expenditure_agent` calls `read_page(page=16)` -> `###### **Budget for FY2024** ###### **Table 2.1** |BLANK|**Revised**<br>**FY2023**|**Estimated**<br>**FY2024**|**Change O**<br>**Revised FY**|**ver**<br>**2023*...`
  - `expenditure_agent` calls `read_page(page=18)` -> `###### _2.6 Special Transfers_ ###### <u>Special Transfers to Households ($2.6 billion)</u> In addition to transfers from the Government’s Operating Expenditure...`
  - `expenditure_agent` calls `sum_amounts(values=[6.0, -3.03])` -> `2.97...`
  - `expenditure_agent` writes the final answer (below)

### Final answer

**No. The FY2024 GST revenue increase does not cover the GST Voucher Fund top-up.** The increase is about $3.0b and the top-up is $6.0b, so the increase covers only about half of it. The shortfall is about $3.0b ($6.0b − $3.03b = $2.97b).

- **GST revenue:** GST is estimated at $19.39b in FY2024, up from $16.36b in Revised FY2023. That is an increase of $3.03b, or 18.5% (Table 2.1, p.16; revenue_agent, p.13 and Table 3.2a p.26).
- **GST Voucher Fund top-up:** The top-up is $6.00b in Estimated FY2024. In Revised FY2023 it was $2.40b (Table 2.1, p.16). The top-up therefore rises by $3.60b year on year.
- **What it funds:** The top-up is meant "to meet the steady state cashflow needs for the enhanced permanent GST Voucher scheme" (p.18).
- **Context:** The $6.0b is part of $20.35b (about $20.4b) of total Top-ups to Endowment and Trust Funds in FY2024 (p.16, p.18).

This is a comparison of two figures only. The source document does not link GST revenue to the top-up.

