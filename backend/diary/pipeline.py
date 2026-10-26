"""LangGraph pipeline: five searchers fan out from START, both synthesisers wait on all five,
assemble waits on both."""

import logging
import operator
import re
from datetime import UTC, date as Date, datetime
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from .agent import AgentResult, model, run_agent
from .prompts import AGENTS, Agent
from .render import render, to_text

log = logging.getLogger(__name__)
BY_ID = {a.agent_id: a for a in AGENTS}
USAGE_KEYS = ("prompt_tokens", "completion_tokens", "cost")


class State(TypedDict):
    date: str
    results: Annotated[dict[str, AgentResult], operator.or_]  # parallel nodes merge, not overwrite
    entry: dict


def briefing(results: dict[str, AgentResult]) -> str:
    done = sorted((BY_ID[i] for i in results if BY_ID[i].searches), key=lambda a: a.order)
    return "\n\n".join(f"## {a.section_title}\n{results[a.agent_id].markdown}" for a in done)


def agent_node(agent: Agent, run=None):
    async def node(state: State) -> dict:
        context = None if agent.searches else briefing(state["results"])
        try:
            result = await (run or run_agent)(agent, state["date"], context=context)
        except Exception:
            # an exception escaping a node aborts the whole graph; one bad agent must not lose six sections
            log.warning("agent %s failed; section omitted", agent.agent_id, exc_info=True)
            return {"results": {}}
        return {"results": {agent.agent_id: result}}
    return node


def strip_title(md: str, title: str) -> str:
    """Models often open with the section title as a heading; the page already renders it."""
    first, _, rest = md.lstrip().partition("\n")
    return rest.lstrip() if first.lstrip("#").strip().lower() == title.lower() and first.startswith("#") else md


def summary(md: str) -> str:
    """First non-heading paragraph: the synthesis prompt already opens with a 2-3 sentence summary."""
    para = next((b for b in md.split("\n\n") if b.strip() and not b.lstrip().startswith("#")), "")
    return re.sub(r"^executive summary:\s*", "", to_text(para), flags=re.I)


def assemble(date: str, results: dict[str, AgentResult]) -> dict:
    sections = []
    for a in sorted((BY_ID[i] for i in results), key=lambda a: a.order):
        r = results[a.agent_id]
        md = strip_title(r.markdown, a.section_title)
        section = {"id": a.section_id, "title": a.section_title, "content": render(md), "order": a.order}
        if r.sources:
            section["sources"] = r.sources
        sections.append(section)

    d = Date.fromisoformat(date)
    synthesis = results.get("synthesis-agent")
    return {
        "metadata": {
            "date": date,
            "title": f"World Digest — {d:%B} {d.day}, {d.year}",
            "summary": summary(synthesis.markdown) if synthesis else "",
            "generatedAt": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "sections": sections,
        # ignored by the frontend; records what produced the entry and what it cost
        "model": model(),
        "usage": {k: sum(r.usage.get(k) or 0 for r in results.values()) for k in USAGE_KEYS},
        "promptVersions": {a.agent_id: a.version for a in AGENTS},
    }


def build(run=None):
    searchers = [a.agent_id for a in AGENTS if a.searches]
    synthesisers = [a.agent_id for a in AGENTS if not a.searches]

    g = StateGraph(State)
    for a in AGENTS:
        g.add_node(a.agent_id, agent_node(a, run))
    g.add_node("assemble", lambda s: {"entry": assemble(s["date"], s["results"])})

    for a in searchers:
        g.add_edge(START, a)
    for s in synthesisers:
        g.add_edge(searchers, s)  # list source = wait for all five
    g.add_edge(synthesisers, "assemble")
    g.add_edge("assemble", END)
    return g.compile()


async def generate(date: str, run=None) -> dict:
    """`run` replaces the model call (for --dry-run); default is the real OpenRouter call."""
    return (await build(run).ainvoke({"date": date, "results": {}}))["entry"]


def check_contract(entry: dict) -> None:
    """The shape website/src/types/index.ts expects. Raises ValueError on the first mismatch."""
    def need(cond, what):
        if not cond:
            raise ValueError(f"contract: {what}")

    meta = entry.get("metadata", {})
    for k in ("date", "title", "summary", "generatedAt"):
        need(isinstance(meta.get(k), str), f"metadata.{k} must be a string")
    need(isinstance(entry.get("sections"), list), "sections must be a list")
    for s in entry["sections"]:
        need(isinstance(s.get("id"), str) and isinstance(s.get("title"), str), "section id/title")
        need(isinstance(s.get("content"), str) and isinstance(s.get("order"), int), "section content/order")
        for src in s.get("sources", []):
            need(src.get("url", "").startswith(("http://", "https://")) and src.get("title"), "source")


def prompts_payload() -> dict:
    return {
        "prompts": [{"agentId": a.agent_id, "agentName": a.agent_name, "description": a.description,
                     "systemPrompt": a.system_prompt, "version": a.version, "lastUpdated": a.last_updated}
                    for a in AGENTS],
        "meta": {"totalAgents": len(AGENTS), "schemaVersion": "1.0.0"},
    }
