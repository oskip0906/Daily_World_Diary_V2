import asyncio
from types import SimpleNamespace as NS

import pytest

from diary import agent as agent_mod
from diary.prompts import AGENTS

SEARCHER = next(a for a in AGENTS if a.searches)
SYNTH = next(a for a in AGENTS if not a.searches)


class FakeCompletions:
    def __init__(self, content="### Hi\n\nBody"):
        self.content, self.calls = content, []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        message = NS(content=self.content, annotations=[NS(url_citation=NS(url="https://a.com", title="A"))])
        usage = NS(model_dump=lambda: {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.01})
        return NS(choices=[NS(message=message, finish_reason="stop")], usage=usage)


@pytest.fixture
def fake(monkeypatch):
    completions = FakeCompletions()
    monkeypatch.setattr(agent_mod, "client", lambda: NS(chat=NS(completions=completions)))
    monkeypatch.setenv("OPENROUTER_MODEL", "vendor/model")
    return completions


def test_searchers_request_web_search(fake):
    result = asyncio.run(agent_mod.run_agent(SEARCHER, "2026-10-24"))
    assert fake.calls[0]["extra_body"]["plugins"][0]["id"] == "web"
    assert fake.calls[0]["model"] == "vendor/model"
    assert result.sources == [{"title": "A", "url": "https://a.com"}]
    assert result.usage["cost"] == 0.01


def test_synthesisers_do_not_search_and_receive_the_briefing(fake):
    asyncio.run(agent_mod.run_agent(SYNTH, "2026-10-24", context="## Political News\nstuff"))
    call = fake.calls[0]
    assert "plugins" not in call["extra_body"]
    assert "## Political News\nstuff" in call["messages"][1]["content"]
    assert call["messages"][0]["content"] == SYNTH.system_prompt


def test_empty_content_raises_so_the_section_is_omitted(fake):
    fake.content = None
    with pytest.raises(ValueError):
        asyncio.run(agent_mod.run_agent(SEARCHER, "2026-10-24"))
