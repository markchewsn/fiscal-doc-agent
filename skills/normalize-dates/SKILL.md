---
name: normalize-dates
description: Normalise free-text dates (e.g. '16 February 2024', '1 April 2023 to 31 March 2024') to ISO YYYY-MM-DD with the deterministic normalize_dates tool. Use before classifying or comparing any date.
metadata:
  include_tools: normalize_dates
---

# Normalise dates

Reading this skill gives you the `normalize_dates` tool (`scripts/normalize_dates.py`).

1. Call `normalize_dates` once with the texts of all items, copied exactly.
2. It returns a JSON list with one entry per text: that text's full dates (day, month and
   year) in order as YYYY-MM-DD, or `[]` if it has none. Day-first, as in Singapore.
3. Use those dates as given; never write or correct a date yourself.
