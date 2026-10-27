import asyncio
from types import SimpleNamespace as NS

import pytest

from diary import agent as agent_mod
from diary.agent import uncite
from diary.prompts import AGENTS
from diary.sources import Item, Material

GATHERER = next(a for a in AGENTS if a.gathers)
SYNTH = next(a for a in AGENTS if not a.gathers)
ITEMS = [Item(f"Headline {n}", f"https://news.example/{n}", f"Outlet {n}") for n in range(1, 8)]


class FakeCompletions:
    def __init__(self, content="### Hi\n\nBody [1]."):
        self.content, self.calls = content, []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        usage = NS(model_dump=lambda: {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.01})
        return NS(choices=[NS(message=NS(content=self.content), finish_reason="stop")], usage=usage)


@pytest.fixture
def fake(monkeypatch):
    completions = FakeCompletions()
    monkeypatch.setattr(agent_mod, "client", lambda: NS(chat=NS(completions=completions)))
    monkeypatch.setenv("OPENROUTER_MODEL", "vendor/model")
    return completions


def test_citation_markers_are_dropped():
    # the page shows no sources; the [n] only keeps the model tied to its material
    assert uncite("Talks stalled [2]. Markets fell [1, 3].") == "Talks stalled. Markets fell."


def test_links_the_model_typed_itself_are_unlinked():
    assert uncite("See [this](https://made.up/page) [1].") == "See this."


def test_gatherers_get_numbered_material_and_no_web_search(fake):
    material = Material(ITEMS[:2], data="S&P 500: 7,600 (+0.3%)", ensure=lambda md: "### IPOs\n\nNone.\n\n" + md)
    result = asyncio.run(agent_mod.run_agent(GATHERER, "2026-10-24", material=material))
    prompt = fake.calls[0]["messages"][1]["content"]
    assert "[1] Headline 1 — Outlet 1" in prompt and "[2] Headline 2 — Outlet 2" in prompt
    assert "S&P 500: 7,600 (+0.3%)" in prompt
    assert "plugins" not in fake.calls[0]["extra_body"]
    # 2026-10-23: even "low" reasoning spent the whole token budget and returned an empty section
    assert fake.calls[0]["extra_body"]["reasoning"] == {"enabled": False}
    assert result.markdown.startswith("### IPOs")  # material.ensure ran
    assert result.markdown.endswith("Body.")  # the [1] marker is gone
    assert result.usage["cost"] == 0.01


def test_synthesisers_receive_the_briefing(fake):
    asyncio.run(agent_mod.run_agent(SYNTH, "2026-10-24", context="## Political News\nstuff"))
    call = fake.calls[0]
    assert "## Political News\nstuff" in call["messages"][1]["content"]
    assert call["messages"][0]["content"] == SYNTH.system_prompt


def test_empty_content_raises_so_the_section_is_omitted(fake):
    fake.content = None
    with pytest.raises(ValueError):
        asyncio.run(agent_mod.run_agent(GATHERER, "2026-10-24", material=Material(ITEMS)))
