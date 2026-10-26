"""LangGraph pipeline: five gatherers (scrape, then write) fan out from START, both synthesisers
wait on all five, assemble waits on both."""

import asyncio
import logging
import operator
import re
from datetime import UTC, date as Date, datetime
from typing import Annotated, TypedDict

import openai
from langgraph.graph import END, START, StateGraph

from .agent import AgentResult, model, run_agent, unlink
from .prompts import AGENTS, Agent
from .render import render, to_text
from .sources import gather

log = logging.getLogger(__name__)
BY_ID = {a.agent_id: a for a in AGENTS}
USAGE_KEYS = ("prompt_tokens", "completion_tokens", "cost")
ACCOUNT_STATUSES = {401, 402, 403}  # bad key, out of credits, key spend cap


class AccountError(RuntimeError):
    """OpenRouter rejected the key itself. Every later call fails too, so the run stops rather than
    writing a partial entry that the write-once store and the Action's skip-if-exists would keep forever."""


class State(TypedDict):
    date: str
    results: Annotated[dict[str, AgentResult], operator.or_]  # parallel nodes merge, not overwrite
    entry: dict


def briefing(results: dict[str, AgentResult]) -> str:
    done = sorted((BY_ID[i] for i in results if BY_ID[i].gathers), key=lambda a: a.order)
    return "\n\n".join(f"## {a.section_title}\n{unlink(results[a.agent_id].markdown)}" for a in done)


def agent_node(agent: Agent, run=None, scrape=None):
    async def node(state: State) -> dict:
        date = state["date"]
        try:
            if agent.gathers:
                # scrapers are blocking I/O; a thread keeps the five gatherers parallel
                material = await asyncio.to_thread(scrape or gather, agent, date)
                result = await (run or run_agent)(agent, date, material=material)
            else:
                result = await (run or run_agent)(agent, date, context=briefing(state["results"]))
        except Exception as e:
            if isinstance(e, openai.APIStatusError) and e.status_code in ACCOUNT_STATUSES:
                raise AccountError(f"OpenRouter rejected the key ({e.status_code}): {e.message}") from e
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


def build(run=None, scrape=None):
    gatherers = [a.agent_id for a in AGENTS if a.gathers]
    synthesisers = [a.agent_id for a in AGENTS if not a.gathers]

    g = StateGraph(State)
    for a in AGENTS:
        g.add_node(a.agent_id, agent_node(a, run, scrape))
    g.add_node("assemble", lambda s: {"entry": assemble(s["date"], s["results"])})

    for a in gatherers:
        g.add_edge(START, a)
    for s in synthesisers:
        g.add_edge(gatherers, s)  # list source = wait for all five
    g.add_edge(synthesisers, "assemble")
    g.add_edge("assemble", END)
    return g.compile()


async def generate(date: str, run=None, scrape=None) -> dict:
    """`run` and `scrape` replace the model call and the scrapers (for --dry-run)."""
    return (await build(run, scrape).ainvoke({"date": date, "results": {}}))["entry"]


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

