"""The normalize-dates skill's tool. SkillsMiddleware binds `normalize_dates` once the agent has
read ../SKILL.md. Also runnable: python normalize_dates.py "16 February 2024" ...

Same name, schema and description as the MCP server's tool (fiscal_doc_agent.mcp_server), over
the same deterministic core, so Part 2's two arms differ only in how the tool is delivered."""

import json
import sys

from fiscal_doc_agent import dates


def normalize_dates(texts: list[str]) -> str:
    """For each free-text string (e.g. '1 April 2023 to 31 March 2024'), find every full date
    and return a JSON list with one entry per input: that text's dates in order as ISO
    YYYY-MM-DD strings, or [] if it has no full date."""
    return json.dumps(dates.normalize_dates(texts))


if __name__ == "__main__":
    print(normalize_dates(sys.argv[1:]))
