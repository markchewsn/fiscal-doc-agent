"""Part 3: document tools, the Revenue / Expenditure agents, and the graphs over them."""

import re
import time
from decimal import Decimal
from functools import cache
from operator import add
from typing import Annotated, Literal, TypedDict

from langchain.agents import create_agent
from langchain.tools import InjectedState, tool
from langchain_core.callbacks import UsageMetadataCallbackHandler
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from pydantic import BaseModel, Field
from rank_bm25 import BM25Okapi

from fiscal_doc_agent.parsing import load_pages


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


@cache
def index() -> tuple[list[dict], BM25Okapi]:
    pages = load_pages()
    return pages, BM25Okapi([tokens(p["markdown"]) for p in pages])


def snippet(text: str, terms: list[str], width: int = 240) -> str:
    """~`width` chars of `text` around the first hit of its rarest query term (terms rarest
    first), whitespace collapsed."""
    text = " ".join(text.split())
    words = [(m.start(), m[0].lower()) for m in re.finditer(r"[A-Za-z0-9]+", text)]
    hit = next((at for term in terms for at, w in words if w == term), 0)
    start = max(0, hit - width // 3)
    return text[start:start + width]


@tool
def search_document(query: str, k: int = 5) -> list[dict]:
    """Keyword (BM25) search over the Source Document's pages. Returns up to k of
    {page, score, snippet}, best first; then read_page the relevant ones."""
    pages, bm25 = index()
    terms = tokens(query)
    scores = bm25.get_scores(terms)
    rarest = sorted(set(terms), key=lambda t: -bm25.idf.get(t, 0))
    best = sorted(range(len(pages)), key=lambda i: -scores[i])[:k]
    return [{"page": pages[i]["page"], "score": round(float(scores[i]), 2),
             "snippet": snippet(pages[i]["markdown"], rarest)}
            for i in best if scores[i] > 0]


@tool
def read_page(page: int) -> str:
    """Full Markdown text (tables included) of one page of the Source Document."""
    pages, _ = index()
    if not 1 <= page <= len(pages):
        return f"No page {page}; pages run 1 to {len(pages)}."
    return pages[page - 1]["markdown"]


@tool
def sum_amounts(values: list[float]) -> float:
    """Exact sum of amounts (all in the same unit). Use instead of adding figures yourself."""
    return float(sum(Decimal(str(v)) for v in values))


# Agents: defined once, shared by every graph so topology is the only variable.
DOC = "Singapore MOF's 'Analysis of Revenue and Expenditure, FY2024' (the Source Document)"
GROUNDING = """Find pages with search_document, then read_page the relevant ones; answer only
from what you read. Give figures with unit and financial year (Actual FY2022, Revised FY2023,
Estimated FY2024; "FY2024" means Estimated FY2024) and cite page numbers. Be concise."""

AGENTS = {
    "revenue_agent": {
        "description": "government revenue: Operating Revenue, tax and non-tax revenue "
                       "streams and their growth, Net Investment Returns Contribution",
        "tools": [search_document, read_page],
    },
    "expenditure_agent": {
        "description": "government spending: ministry expenditure, Special Transfers, Top-ups "
                       "to Endowment and Trust Funds (e.g. National Research Fund) and what they fund",
        "tools": [search_document, read_page, sum_amounts],
    },
}
for name, a in AGENTS.items():
    a["prompt"] = (f"You are the {name.replace('_', ' ').title()}, a specialist in "
                   f"{a['description']}, answering from {DOC}.\n{GROUNDING}")
AGENTS["expenditure_agent"]["prompt"] += ("\nUse sum_amounts for every total; never add "
                                          "figures yourself.")
AgentName = Literal["revenue_agent", "expenditure_agent"]

TRACE_RESULT_CHARS = 300


def build_agent(name: str, model, extra_tools=()):
    """The `name` agent with its shared prompt and tools, plus graph-specific `extra_tools`
    (e.g. handoffs)."""
    a = AGENTS[name]
    return create_agent(model, [*a["tools"], *extra_tools], system_prompt=a["prompt"])


def agent_events(agent: str, messages) -> list[dict]:
    """Trace events (tool calls with results, then the answer) from one agent run."""
    results = {m.tool_call_id: m.text for m in messages if isinstance(m, ToolMessage)}
    events = [{"type": "tool_call", "agent": agent, "tool": c["name"], "args": c["args"],
               "result": results.get(c["id"], "")[:TRACE_RESULT_CHARS]}
              for m in messages if isinstance(m, AIMessage) for c in m.tool_calls]
    return events + [{"type": "agent_answer", "agent": agent, "text": messages[-1].text}]


def briefing(query: str, reports: list[dict], task: str = "") -> str:
    """One human turn carrying the question, findings so far and (for an agent) its task."""
    parts = [f"Question: {query}"]
    parts += [f"Findings from {r['agent']}:\n{r['text']}" for r in reports]
    if task:
        parts.append(f"Your task: {task}")
    return "\n\n".join(parts)


# Supervisor graph: a central router decides every hop and writes the final answer.
SUPERVISOR_PROMPT = f"""You supervise specialist agents answering a question about {DOC}.
Agents:
""" + "\n".join(f"- {n}: {a['description']}" for n, a in AGENTS.items()) + """
Each turn, decide who acts next. Route to the agent whose specialism covers a part of the
question not yet answered by the findings; in `reason`, say why and what it must find. Do not
re-route an agent for something it already answered. Choose FINISH once the findings cover
every part of the question."""

SYNTHESIS_PROMPT = f"""You write the final answer to a question about {DOC} from specialist
agents' findings. Write one comprehensive, well-structured answer covering every part of the
question, keeping their figures, units, financial years and page citations. Use only the
findings; say if something could not be found."""


class Route(BaseModel):
    """The supervisor's routing decision."""

    next: Literal["revenue_agent", "expenditure_agent", "FINISH"]
    reason: str = Field(description="Why this choice; for an agent, what it must find.")


class State(TypedDict):
    query: str
    task: str  # the supervisor's latest instruction
    reports: Annotated[list[dict], add]  # {agent, text}, in order
    trace: Annotated[list[dict], add]
    answer: str


def supervisor_graph(model):
    router = model.with_structured_output(Route, method="json_schema")

    def supervisor(state: State) -> Command[AgentName | Literal["__end__"]]:
        brief = briefing(state["query"], state["reports"])
        route = router.invoke([("system", SUPERVISOR_PROMPT), ("human", brief)])
        event = {"type": "route", "next": route.next, "reason": route.reason}
        if route.next != "FINISH":
            return Command(goto=route.next, update={"task": route.reason, "trace": [event]})
        answer = model.invoke([("system", SYNTHESIS_PROMPT), ("human", brief)]).text
        return Command(goto=END, update={"answer": answer, "trace": [
            event, {"type": "final_answer", "text": answer}]})

    def agent_node(name: str):
        agent = build_agent(name, model)

        def run(state: State) -> Command[Literal["supervisor"]]:
            brief = briefing(state["query"], state["reports"], state["task"])
            messages = agent.invoke({"messages": [("human", brief)]})["messages"]
            report = {"agent": name, "text": messages[-1].text}
            return Command(goto="supervisor",
                           update={"reports": [report], "trace": agent_events(name, messages)})

        return run

    graph = StateGraph(State)
    graph.add_node("supervisor", supervisor)
    for name in AGENTS:
        graph.add_node(name, agent_node(name))
    graph.add_edge(START, "supervisor")
    return graph.compile()


# Swarm graph: no central router. A one-call entry picks the first agent; agents hand off
# directly to a peer, and whichever agent answers without handing off writes the final answer.
ENTRY_PROMPT = f"""Pick the specialist agent that should start answering a question about {DOC}.
Agents:
""" + "\n".join(f"- {n}: {a['description']}" for n, a in AGENTS.items())

SWARM_TASK = """Research only the parts of the question within your specialism. Do not research
or answer a part outside it yourself: if any such part is not covered by the findings above, you
must call {handoff} with your findings (figures, units, financial years, page citations) and
what {peer} must find. Only when the findings above and yours cover every part, write the final
answer: one comprehensive answer to the whole question, combining them."""


class Entry(BaseModel):
    """The swarm entry's choice of first agent."""

    agent: AgentName
    reason: str = Field(description="Why this agent should start.")


def handoff_tool(name: str, peer: str):
    """`transfer_to_<peer>`: ends `name`'s run and sends the question straight to `peer`."""

    @tool(f"transfer_to_{peer}")
    def transfer(findings: str, task: str, state: Annotated[dict, InjectedState]) -> Command:
        """Hand the question to a peer agent once your part is answered. findings: your answer
        so far with figures and page citations; task: what the peer must still find."""
        own = [e for e in agent_events(name, state["messages"])
               if e["type"] == "tool_call" and e["tool"] != f"transfer_to_{peer}"]
        return Command(goto=peer, graph=Command.PARENT, update={
            "task": task, "reports": [{"agent": name, "text": findings}],
            "trace": [*own, {"type": "handoff", "agent": name, "next": peer, "reason": task,
                               "findings": findings}]})

    transfer.description += f" The peer is {peer}: {AGENTS[peer]['description']}."
    return transfer


def swarm_graph(model):
    picker = model.with_structured_output(Entry, method="json_schema")

    def entry(state: State) -> Command[AgentName]:
        pick = picker.invoke([("system", ENTRY_PROMPT), ("human", state["query"])])
        return Command(goto=pick.agent, update={"trace": [
            {"type": "entry", "next": pick.agent, "reason": pick.reason}]})

    def agent_node(name: str):
        peer = next(n for n in AGENTS if n != name)
        handoff = handoff_tool(name, peer)
        agent = build_agent(name, model, [handoff])
        task = SWARM_TASK.format(handoff=handoff.name, peer=peer)

        # A handoff raises out of agent.invoke as a parent Command; reaching the return
        # means this agent answered without handing off, so it is the last one.
        def run(state: State) -> Command[AgentName | Literal["__end__"]]:
            brief = briefing(state["query"], state["reports"], "\n\n".join(
                filter(None, [state["task"], task])))
            messages = agent.invoke({"messages": [("human", brief)]})["messages"]
            events = agent_events(name, messages)
            answer = events.pop()["text"]
            return Command(goto=END, update={"answer": answer, "trace": [
                *events, {"type": "final_answer", "agent": name, "text": answer}]})

        return run

    graph = StateGraph(State)
    graph.add_node("entry", entry)
    for name in AGENTS:
        graph.add_node(name, agent_node(name))
    graph.add_edge(START, "entry")
    return graph.compile()


GRAPHS = {"supervisor": supervisor_graph, "swarm": swarm_graph}
RECURSION_LIMIT = 25  # graph steps per run; caps runaway routing loops


class UsageCounter(UsageMetadataCallbackHandler):
    """Token usage by model, plus the number of LLM calls."""

    llm_calls = 0

    def on_llm_end(self, response, **kwargs):
        super().on_llm_end(response, **kwargs)
        self.llm_calls += 1


def run_graph(kind: str, query: str, model) -> dict:
    """Answer `query` with the `kind` graph; returns {answer, trace, usage, llm_calls, latency_s}."""
    if kind not in GRAPHS:
        raise ValueError(f"unknown graph {kind!r}; choose from {sorted(GRAPHS)}")
    graph, counter = GRAPHS[kind](model), UsageCounter()
    start = time.perf_counter()
    state = graph.invoke({"query": query, "task": "", "reports": [], "trace": []},
                         {"callbacks": [counter], "recursion_limit": RECURSION_LIMIT})
    return {"answer": state["answer"], "trace": state["trace"], "usage": counter.usage_metadata,
            "llm_calls": counter.llm_calls, "latency_s": round(time.perf_counter() - start, 2)}
