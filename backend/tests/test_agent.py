import asyncio
from types import SimpleNamespace as NS

import pytest

from diary import agent as agent_mod
from diary.agent import cite
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


def test_citations_become_links_to_the_scraped_item():
    md, _ = cite("Talks stalled [2].", ITEMS)
    assert md == "Talks stalled [Outlet 2](https://news.example/2)."


def test_grouped_citations_each_become_a_link():
    md, _ = cite("Markets fell [1, 3].", ITEMS)
    assert "[Outlet 1](https://news.example/1) [Outlet 3](https://news.example/3)" in md


def test_unknown_citation_numbers_are_dropped():
    assert cite("Rumour [42].", ITEMS)[0] == "Rumour."


def test_links_the_model_typed_itself_are_unlinked():
    # the model never supplies a URL: only scraped items become links
    assert cite("See [this](https://made.up/page) [1].", ITEMS)[0] == "See this [Outlet 1](https://news.example/1)."


def test_sources_are_the_cited_items_in_order_capped_at_five():
    _, sources = cite("a [3] b [1] c [3] d [2] e [4] f [5] g [6]", ITEMS)
    assert [s["url"][-1] for s in sources] == ["3", "1", "2", "4", "5"]
    assert sources[0] == {"title": "Headline 3", "url": "https://news.example/3"}


def test_uncited_output_falls_back_to_the_top_items():
    _, sources = cite("No citations.", ITEMS)
    assert [s["url"][-1] for s in sources] == ["1", "2", "3", "4", "5"]


def test_gatherers_get_numbered_material_and_no_web_search(fake):
    material = Material(ITEMS[:2], data="S&P 500: 7,600 (+0.3%)", ensure=lambda md: "### IPOs\n\nNone.\n\n" + md)
    result = asyncio.run(agent_mod.run_agent(GATHERER, "2026-10-24", material=material))
    prompt = fake.calls[0]["messages"][1]["content"]
    assert "[1] Headline 1 — Outlet 1" in prompt and "[2] Headline 2 — Outlet 2" in prompt
    assert "S&P 500: 7,600 (+0.3%)" in prompt
    assert "plugins" not in fake.calls[0]["extra_body"]
    assert result.markdown.startswith("### IPOs")  # material.ensure ran
    assert "[Outlet 1](https://news.example/1)" in result.markdown
    assert result.sources == [{"title": "Headline 1", "url": "https://news.example/1"}]
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
