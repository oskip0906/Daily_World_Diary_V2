"""LangGraph pipeline: five gatherers (scrape, then write) fan out from START, both synthesisers
wait on all five, the designer reads the finished entry, and assemble writes it up."""

import asyncio
import logging
import operator
import re
from datetime import UTC, date as Date, datetime
from typing import Annotated, TypedDict

import openai
from langgraph.graph import END, START, StateGraph

from .agent import AgentResult, model, run_agent, unlink
from .design import run_design
from .prompts import AGENTS, Agent
from .render import render, to_text
from .sources import gather

log = logging.getLogger(__name__)
BY_ID = {a.agent_id: a for a in AGENTS}
USAGE_KEYS = ("prompt_tokens", "completion_tokens", "cost")
SUMMARY_AGENT = "synthesis-agent"  # its paragraph becomes metadata.summary, not a section
ACCOUNT_STATUSES = {401, 402, 403}  # bad key, out of credits, key spend cap


class AccountError(RuntimeError):
    """OpenRouter rejected the key itself. Every later call fails too, so the run stops rather than
    writing a partial entry that the write-once store and the Action's skip-if-exists would keep forever."""


class State(TypedDict):
    date: str
    results: Annotated[dict[str, AgentResult], operator.or_]  # parallel nodes merge, not overwrite
    theme: dict | None
    design_usage: dict
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


def page_sections(results: dict[str, AgentResult]) -> list[tuple[Agent, str]]:
    """(agent, markdown) for every section the page shows, in page order."""
    shown = sorted((BY_ID[i] for i in results if i != SUMMARY_AGENT), key=lambda a: a.order)
    return [(a, strip_title(results[a.agent_id].markdown, a.section_title)) for a in shown]


def title(date: str) -> str:
    d = Date.fromisoformat(date)
    return f"World Digest — {d:%B} {d.day}, {d.year}"


def summary_of(results: dict[str, AgentResult]) -> str:
    synthesis = results.get(SUMMARY_AGENT)
    return summary(synthesis.markdown) if synthesis else ""


def design_node(design=None):
    async def node(state: State) -> dict:
        results = state["results"]
        sections = [(a.section_id, a.section_title, md) for a, md in page_sections(results)]
        if not sections:
            return {"theme": None, "design_usage": {}}
        try:
            theme, usage = await (design or run_design)(state["date"], title(state["date"]), summary_of(results), sections)
        except Exception:
            # the theme is decoration: a failure here must not lose the entry
            log.warning("design failed; the page uses the base design", exc_info=True)
            return {"theme": None, "design_usage": {}}
        return {"theme": theme, "design_usage": usage}
    return node


def assemble(date: str, results: dict[str, AgentResult], theme: dict | None = None,
             design_usage: dict | None = None) -> dict:
    sections = [{"id": a.section_id, "title": a.section_title, "content": render(md), "order": a.order}
                for a, md in page_sections(results)]
    usages = [r.usage for r in results.values()] + [design_usage or {}]
    entry = {
        "metadata": {
            "date": date,
            "title": title(date),
            "summary": summary_of(results),
            "generatedAt": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "sections": sections,
        # ignored by the frontend; records what produced the entry and what it cost
        "model": model(),
        "usage": {k: sum(u.get(k) or 0 for u in usages) for k in USAGE_KEYS},
        "promptVersions": {a.agent_id: a.version for a in AGENTS},
    }
    if theme:
        entry["theme"] = theme
    return entry


def build(run=None, scrape=None, design=None):
    gatherers = [a.agent_id for a in AGENTS if a.gathers]
    synthesisers = [a.agent_id for a in AGENTS if not a.gathers]

    g = StateGraph(State)
    for a in AGENTS:
        g.add_node(a.agent_id, agent_node(a, run, scrape))
    g.add_node("design", design_node(design))
    g.add_node("assemble", lambda s: {"entry": assemble(s["date"], s["results"], s.get("theme"), s.get("design_usage"))})

    for a in gatherers:
        g.add_edge(START, a)
    for s in synthesisers:
        g.add_edge(gatherers, s)  # list source = wait for all five
    g.add_edge(synthesisers, "design")
    g.add_edge("design", "assemble")
    g.add_edge("assemble", END)
    return g.compile()


async def generate(date: str, run=None, scrape=None, design=None) -> dict:
    """`run`, `scrape` and `design` replace the model calls and the scrapers (for --dry-run)."""
    return (await build(run, scrape, design).ainvoke({"date": date, "results": {}}))["entry"]


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
    theme = entry.get("theme")
    if theme is not None:
        need(all(isinstance(theme.get(k), str) and theme[k] for k in ("name", "note", "css")), "theme name/note/css")
        need("<" not in theme["css"], "theme css must not contain <")

