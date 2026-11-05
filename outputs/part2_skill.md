# Part 2 dates (skill arm)

Model: `global.anthropic.claude-sonnet-5-5`  
Reference date: 2024-01-01  
Latency: 8.56s

| Original text | Normalized | Status | Reasoning |
|---|---|---|---|
| Distributed on Budget Day: 16 February 2024 | 2024-02-16 | **Upcoming** | Single distribution date, not a period; 2024-02-16 is after the reference date 2024-01-01, so Upcoming. |
| 15 February 2008 | 2008-02-15 | **Expired** | Single cut-off date, not a period; 2008-02-15 is before 2024-01-01, so Expired. The rule (Estate Duty does not apply to a person who dies after this date) is still in force on 2024-01-01. |

## Evidence

- `distribution_date` p1: `Distributed on Budget Day: 16 February 2024`
- `estate_duty_date` p36: `Estate Duty does not apply to a person who dies after 15 February 2008.`

## Token usage and cost

| Stage | Input | Output | Cost (USD) |
|---|---|---|---|
| extract | 32,314 | 134 | 0.0660 |
| agent | 8,609 | 423 | 0.0185 |
| robustness_demo | 9,014 | 868 | 0.0124 |

Prices 2026-11-05, https://platform.claude.com/docs/en/about-claude/pricing

## Robustness demo (periods, separate from the required output)

| Original text | Normalized | Status | Reasoning |
|---|---|---|---|
| Financial Year 2022: 1 April 2022 to 31 March 2023 | 2022-04-01 | **Expired** | Start of period 2022-04-01 to 2023-03-31; period ended before 2024-01-01, so not active. Date is before reference date. |
| Financial Year 2022: 1 April 2022 to 31 March 2023 | 2023-03-31 | **Expired** | End of period 2022-04-01 to 2023-03-31; period ended before 2024-01-01, so not active. |
| Financial Year 2023: 1 April 2023 to 31 March 2024 | 2023-04-01 | **Ongoing** | Start of period 2023-04-01 to 2024-03-31, which is active on 2024-01-01 (starts before, ends after). |
| Financial Year 2023: 1 April 2023 to 31 March 2024 | 2024-03-31 | **Ongoing** | End of period 2023-04-01 to 2024-03-31, which is active on 2024-01-01. |
| Financial Year 2024: 1 April 2024 to 31 March 2025 | 2024-04-01 | **Upcoming** | Period 2024-04-01 to 2025-03-31 starts after 2024-01-01, so not active; date is after reference date. |
| Financial Year 2024: 1 April 2024 to 31 March 2025 | 2025-03-31 | **Upcoming** | End of period starting after 2024-01-01; period not active and date is after reference date. |
