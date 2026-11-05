# Part 2: MCP vs Skill tool delivery

Model: `global.anthropic.claude-sonnet-5-5`. Same deepagents harness, prompt and `normalize_dates` function (same name, schema and description) in both arms; only the delivery differs. MCP: bound from the first agent turn via a local stdio MCP server. Skill: listed by name and description in the system prompt, bound only after the agent reads `skills/normalize-dates/SKILL.md`.

| Stage | MCP input | Skill input | MCP output | Skill output | MCP USD | Skill USD |
|---|---|---|---|---|---|---|
| extract | 32,314 | 32,314 | 134 | 134 | 0.0660 | 0.0660 |
| agent | 3,881 | 8,609 | 347 | 423 | 0.0086 | 0.0185 |
| robustness_demo | 4,180 | 9,014 | 849 | 868 | 0.0101 | 0.0124 |

`extract` is identical in both arms (no tools); `agent` and `robustness_demo` are where tool delivery matters.

Latency (extraction + agent on the two document dates): MCP 7.92s, Skill 8.56s.

Date statuses agree across arms: **yes**

## Why the Skill arm uses more tokens

Progressive disclosure defers a tool's schema until the skill is read. That pays off only when the deferred schemas are bigger than the fixed cost of the skill mechanism. Here the skill is always needed, and it defers one small tool, so the fixed cost dominates:

- **Deferred:** only the `normalize_dates` schema, a short tool definition, and only on the first agent turn.
- **Added every turn:** the skills section deepagents appends to the system prompt (the skill list plus generic instructions on how to use skills), which is several times longer than that schema.
- **Added turn:** the agent must call `read_file` on SKILL.md before it can normalise, so a run takes one more model call. Each call re-sends the whole context, and the SKILL.md body stays in history for later turns. The extra `read_file` call is also why output tokens are higher.
- **Cache:** on Bedrock, deepagents can't add a tool mid-conversation, so the tool list changes after the read and the cached prompt prefix is rebuilt (more cache writes). Native Anthropic and OpenAI models add it without breaking the cache.

Skills would be better when an agent has many tools, or tools it seldom needs: the MCP arm pays for every schema on every turn, while the skills section grows by one line per skill.

Caveat: one run per arm. USD includes prompt-cache reads and writes, whose split depends on cache state, so the token columns are the cleaner comparison.

Prices 2026-11-05, https://platform.claude.com/docs/en/about-claude/pricing
