# Part 3: Supervisor vs Swarm

Model: `global.anthropic.claude-sonnet-5-5`. Both graphs use the same two agents (same system prompts and document tools); only the topology differs. The swarm also gives each agent a `transfer_to_<peer>` tool and tells it when to hand off. In the supervisor, the supervisor tells each agent what to find. Supervisor: a central LLM router picks every hop and a final synthesis call writes the answer. Swarm: one entry call picks the first agent, agents hand off directly via `transfer_to_<peer>` tools, and the last active agent writes the answer.

| Query / graph | Agent path | LLM calls | Input tokens | Output tokens | Cost (USD) | Latency (s) |
|---|---|---|---|---|---|---|
| **Q1**: What are the key government revenue streams, and how will the Budget for the Future Energy Fund be supported? | | | | | | |
| supervisor | revenue > expenditure | 13 | 56,185 | 6,158 | 0.1739 | 48.82 |
| swarm | revenue > expenditure | 7 | 19,648 | 2,612 | 0.0654 | 22.71 |
| **Q2**: Which revenue streams grow fastest in FY2024? | | | | | | |
| supervisor | revenue | 6 | 11,689 | 2,410 | 0.0475 | 19.17 |
| swarm | revenue | 4 | 7,984 | 1,285 | 0.0288 | 12.23 |
| **Q3**: What is the total of FY2024 fund Top-ups and which is largest? | | | | | | |
| supervisor | expenditure | 7 | 12,943 | 1,479 | 0.0407 | 14.44 |
| swarm | expenditure | 5 | 8,595 | 578 | 0.0230 | 7.6 |
| **Q4**: Does the FY2024 GST revenue increase cover the GST Voucher Fund Top-up? | | | | | | |
| supervisor | revenue > expenditure | 11 | 32,794 | 3,276 | 0.0983 | 30.35 |
| swarm | revenue > expenditure | 8 | 26,038 | 1,441 | 0.0665 | 16.56 |
| **Total supervisor** | | 37 | 113,611 | 13,323 | 0.3605 | 112.78 |
| **Total swarm** | | 24 | 62,265 | 5,916 | 0.1837 | 59.1 |

## Where the difference comes from

- **Central calls:** per query the supervisor makes one routing call per agent run, a FINISH routing call and a synthesis call; each re-sends the question and every agent's findings so far. The swarm makes one small entry call, then each agent passes the question straight to the next agent itself.
- **Synthesis:** the supervisor's final answer is a separate call that re-reads all findings and rewrites them, roughly doubling output tokens. In the swarm the last agent writes the final answer in the turn it would have used to report back.
- **Division of labour:** the supervisor decides which agent handles each part; swarm agents decide for themselves, and the document tools reach every page: in Q1 the revenue agent searched for the Future Energy Fund before handing off.

Caveat: one run per graph. Agent turn counts vary between runs, so differences of a call or two per query are noise, but the supervisor's extra calls happen on every query.

Prices 2026-10-06, https://platform.claude.com/docs/en/about-claude/pricing
