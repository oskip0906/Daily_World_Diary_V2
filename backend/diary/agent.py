"""One OpenRouter call per agent -> (markdown, usage)."""

import os
import re
from dataclasses import dataclass, field
from functools import cache

from openai import AsyncOpenAI

from .prompts import Agent
from .sources import Material

MAX_TOKENS = 8000
FORMAT = ("Write in Markdown. Start headings at ### (the page already shows the section title). "
          "No preamble, no sign-off.")
CITATION = re.compile(r"\s*\[(\d+(?:\s*,\s*\d+)*)\]")
MODEL_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")


@dataclass
class AgentResult:
    markdown: str
    usage: dict = field(default_factory=dict)


@cache
def client() -> AsyncOpenAI:
    return AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.environ["OPENROUTER_API_KEY"])


def model() -> str:
    return os.environ["OPENROUTER_MODEL"]


def unlink(md: str) -> str:
    return MODEL_LINK.sub(r"\1", md)


def numbered(material: Material) -> str:
    rows = [f"[{n}] {i.title} — {i.publisher}" + (f" ({i.detail})" if i.detail else "")
            for n, i in enumerate(material.items, 1)]
    return "\n\n".join(p for p in (material.data, "Numbered items:\n" + "\n".join(rows)) if p)


def task(agent: Agent, date: str, context: str | None = None, material: Material | None = None) -> str:
    if material is not None:
        return (f"Write the {agent.section_title} section of Daily World Diary for {date}, covering the 24 hours "
                f"up to the morning of {date}. Use only the material below; add no facts from elsewhere. "
                f"Cite the numbered items you use as [n] right after the sentence they support. "
                f"{FORMAT}\n\n{numbered(material)}")
    return (f"These are the {date} sections of Daily World Diary:\n\n{context}\n\n"
            f"Write the {agent.section_title} section from them. " + FORMAT)


def uncite(md: str) -> str:
    """The page shows no sources: drop the [n] markers and any link the model typed itself.
    The prompt still asks for [n] so the model keeps each claim tied to a scraped item."""
    return CITATION.sub("", unlink(md))


async def run_agent(agent: Agent, date: str, context: str | None = None,
                    material: Material | None = None) -> AgentResult:
    resp = await client().chat.completions.create(
        model=model(),
        messages=[{"role": "system", "content": agent.system_prompt},
                  {"role": "user", "content": task(agent, date, context, material)}],
        max_tokens=MAX_TOKENS,
        extra_headers={"X-Title": "Daily World Diary"},
        # the agents summarise material they're handed; reasoning (even "low") could spend the whole
        # max_tokens budget and return an empty section
        extra_body={"reasoning": {"enabled": False}},
    )
    message = resp.choices[0].message
    if not (message.content or "").strip():
        raise ValueError(f"{agent.agent_id} returned no content (finish_reason={resp.choices[0].finish_reason})")
    md = uncite(message.content.strip())
    if material is not None:
        md = material.ensure(md)
    usage = resp.usage.model_dump() if resp.usage else {}
    return AgentResult(md, usage)
