"""Local stdio MCP server exposing `normalize_dates`. Run: python -m fiscal_doc_agent.mcp_server"""

import json

from mcp.server.fastmcp import FastMCP

from fiscal_doc_agent import dates

mcp = FastMCP("dates")


@mcp.tool()
def normalize_dates(texts: list[str]) -> str:
    """For each free-text string (e.g. '1 April 2023 to 31 March 2024'), find every full date
    and return a JSON list with one entry per input: that text's dates in order as ISO
    YYYY-MM-DD strings, or [] if it has no full date."""
    # A JSON string, not list[list[str]]: FastMCP sends a returned list as one flat text block
    # per date, so the model would lose which dates belong to which text (and the [] entries).
    return json.dumps(dates.normalize_dates(texts))


if __name__ == "__main__":
    mcp.run()
