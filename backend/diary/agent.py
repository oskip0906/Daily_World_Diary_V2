"""One OpenRouter call per agent -> (markdown, sources, usage)."""

import os
from dataclasses import dataclass, field
from functools import cache

from openai import AsyncOpenAI

from .prompts import Agent

MAX_TOKENS = 8000  # includes reasoning tokens; 4000 left some sections empty
MAX_SOURCES = 5
# OpenRouter runs the search server-side (Exa for non-native models) and returns url_citation annotations
WEB_SEARCH = {"plugins": [{"id": "web", "max_results": MAX_SOURCES}]}
FORMAT = ("Write in Markdown. Start headings at ### (the page already shows the section title). "
          "No preamble, no sign-off.")


@dataclass
class AgentResult:
    markdown: str
    sources: list[dict] = field(default_factory=list)
    usage: dict = field(default_factory=dict)


@cache
def client() -> AsyncOpenAI:
    return AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.environ["OPENROUTER_API_KEY"])


def model() -> str:
    return os.environ["OPENROUTER_MODEL"]


def task(agent: Agent, date: str, context: str | None) -> str:
    if context is None:
        return (f"Write the {agent.section_title} section of Daily World Diary for {date}, covering the "
                f"24 hours up to the morning of {date}. Report only events found in the search results. "
                + FORMAT)
    return (f"These are the {date} sections of Daily World Diary:\n\n{context}\n\n"
            f"Write the {agent.section_title} section from them. " + FORMAT)


def harvest(message) -> list[dict]:
    """Sources come only from the gateway's citations: the model never types a URL, so it can't invent one."""
    out, seen = [], set()
    for a in getattr(message, "annotations", None) or []:
        c = getattr(a, "url_citation", a)  # Chat Completions nests it; Responses API is flat
        url = getattr(c, "url", None)
        if url and url.startswith(("http://", "https://")) and url not in seen:
            seen.add(url)
            out.append({"title": getattr(c, "title", None) or url, "url": url})
    return out[:MAX_SOURCES]


async def run_agent(agent: Agent, date: str, context: str | None = None) -> AgentResult:
    resp = await client().chat.completions.create(
        model=model(),
        messages=[{"role": "system", "content": agent.system_prompt},
                  {"role": "user", "content": task(agent, date, context)}],
        max_tokens=MAX_TOKENS,
        extra_headers={"X-Title": "Daily World Diary"},
        # reasoning tokens count against max_tokens; keep them small so the section itself fits
        extra_body={"reasoning": {"effort": "low"}, **(WEB_SEARCH if agent.searches else {})},
    )
    message = resp.choices[0].message
    if not (message.content or "").strip():
        raise ValueError(f"{agent.agent_id} returned no content (finish_reason={resp.choices[0].finish_reason})")
    usage = resp.usage.model_dump() if resp.usage else {}
    return AgentResult(message.content.strip(), harvest(message), usage)
