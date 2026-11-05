# Part 2 dates (mcp arm)

Model: `global.anthropic.claude-sonnet-5-5`  
Reference date: 2024-01-01  
Latency: 7.92s

| Original text | Normalized | Status | Reasoning |
|---|---|---|---|
| Distributed on Budget Day: 16 February 2024 | 2024-02-16 | **Upcoming** | Single date, not part of a period. 2024-02-16 is after the reference date 2024-01-01, so it is Upcoming. |
| 15 February 2008 | 2008-02-15 | **Expired** | Single cut-off date, not part of a period. 2008-02-15 is before 2024-01-01, so it is Expired. The rule it marks (Estate Duty does not apply to a person who dies after this date) is still in force on 2024-01-01. |

## Evidence

- `distribution_date` p1: `Distributed on Budget Day: 16 February 2024`
- `estate_duty_date` p36: `Estate Duty does not apply to a person who dies after 15 February 2008.`

## Token usage and cost

| Stage | Input | Output | Cost (USD) |
|---|---|---|---|
| extract | 32,314 | 134 | 0.0660 |
| agent | 3,881 | 347 | 0.0078 |
| robustness_demo | 4,180 | 849 | 0.0102 |

Prices 2026-10-06, https://platform.claude.com/docs/en/about-claude/pricing

## Robustness demo (periods, separate from the required output)

| Original text | Normalized | Status | Reasoning |
|---|---|---|---|
| Financial Year 2022: 1 April 2022 to 31 March 2023 | 2022-04-01 | **Expired** | Start of FY2022 period; the period ended 2023-03-31, so it is not active on 2024-01-01 and the date is before the reference date. |
| Financial Year 2022: 1 April 2022 to 31 March 2023 | 2023-03-31 | **Expired** | End of FY2022 period; the period is not active on 2024-01-01 and the date is before the reference date. |
| Financial Year 2023: 1 April 2023 to 31 March 2024 | 2023-04-01 | **Ongoing** | Start of FY2023 period, which started on or before 2024-01-01 and ends 2024-03-31, so it is active on the reference date. |
| Financial Year 2023: 1 April 2023 to 31 March 2024 | 2024-03-31 | **Ongoing** | End of FY2023 period, which is active on 2024-01-01 (starts 2023-04-01, ends after the reference date). |
| Financial Year 2024: 1 April 2024 to 31 March 2025 | 2024-04-01 | **Upcoming** | Start of FY2024 period; the period has not started by 2024-01-01 so it is not active, and the date is after the reference date. |
| Financial Year 2024: 1 April 2024 to 31 March 2025 | 2025-03-31 | **Upcoming** | End of FY2024 period; the period is not active on 2024-01-01 and the date is after the reference date. |
