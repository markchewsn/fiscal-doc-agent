"""Deterministic date normalisation: free texts -> every full date in each, as YYYY-MM-DD."""

import re
from datetime import date

from dateutil import parser

# Full dates only (day, month and year): '16 February 2024', '16 Feb 2024', '16/02/2024',
# '2024-02-16'. Partial dates such as 'February 2024' or 'FY2023' never match.
FULL_DATE = re.compile(
    r"""
    \b                      # start at a word boundary, so '2016 Feb 2024' can't match '16 Feb 2024'
    (                       # three alternatives, tried left to right at each position:
        \d{4}-\d{2}-\d{2}   #   ISO: 4-digit year, 2-digit month, 2-digit day   '2024-02-16'
      | \d{1,2}/\d{1,2}/\d{4}
                            #   slashes: day/month/year, 1-2 digit day/month    '16/02/2024'
      | \d{1,2}\s+          #   words: 1-2 digit day, whitespace,
        [A-Za-z]{3,9}\.?    #     a 3-9 letter month name or abbreviation
                            #     ('Feb', 'February', 'Sept.'), optional dot,
        \s+\d{4}            #     whitespace, 4-digit year                      '16 February 2024'
    )
    \b                      # end at a word boundary, so '16 Feb 20245' can't match
    """,
    re.VERBOSE,  # lets the pattern span lines with these comments; plain spaces are ignored
)
# Any 3-9 letter word matches the month slot ('3 apples 2024'); dateutil then rejects those.


def normalize_dates(texts: list[str]) -> list[list[str]]:
    """For each text, every full date in it, in order, as YYYY-MM-DD (day-first, as in
    Singapore). A text with no full date gets an empty list."""
    return [dates_in(t) for t in texts]


def dates_in(text: str) -> list[str]:
    found = []
    for match in FULL_DATE.finditer(text):
        s = match.group()
        try:
            d = date.fromisoformat(s) if "-" in s else parser.parse(s, dayfirst=True).date()
        except ValueError:  # e.g. '3 apples 2024'
            continue
        found.append(d.isoformat())
    return found
