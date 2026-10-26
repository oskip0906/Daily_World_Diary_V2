import asyncio
from datetime import datetime

import pytest

from diary import pipeline
from diary.agent import AgentResult
from diary.prompts import AGENTS
from diary.sources import Item, Material

GATHERERS = [a for a in AGENTS if a.gathers]
SECTION_IDS = ["political-news", "financial-news", "entertainment-news", "music-releases",
               "stock-analysis", "daily-summary", "outlook"]


@pytest.fixture
def contexts(monkeypatch):
    """Stub every scrape and agent; record the context and material each agent was given."""
    seen = {}

    async def fake_run_agent(agent, date, context=None, material=None):
        seen[agent.agent_id] = context
        seen[agent.agent_id, "material"] = material
        if agent.agent_id == "synthesis-agent":
            md = "### Executive Summary\n\nThe day in **brief**.\n\nMore detail."
        else:
            md = f"### {agent.agent_name}\n\nBody of {agent.agent_id}."
        sources = [{"title": "S", "url": "https://s.com"}] if agent.gathers else []
        return AgentResult(md, sources, {"prompt_tokens": 100, "completion_tokens": 10, "cost": 0.01})

    monkeypatch.setattr(pipeline, "run_agent", fake_run_agent)
    monkeypatch.setattr(pipeline, "gather", lambda agent, date: Material(
        [Item(f"{agent.agent_id} story", f"https://news.example/{agent.agent_id}", "Outlet")]))
    monkeypatch.setenv("OPENROUTER_MODEL", "vendor/model")
    return seen


def generate(date="2026-10-24"):
    return asyncio.run(pipeline.generate(date))


def test_sections_match_the_frontend_contract(contexts):
    entry = generate()
    assert [s["id"] for s in entry["sections"]] == SECTION_IDS
    assert [s["order"] for s in entry["sections"]] == [1, 2, 3, 4, 5, 6, 7]
    assert entry["sections"][0]["title"] == "Political News"
    assert entry["sections"][0]["content"].startswith("<h3>")
    pipeline.check_contract(entry)


def test_synthesisers_receive_all_five_gatherer_sections(contexts):
    generate()
    for synth in ("synthesis-agent", "outlook-agent"):
        for a in GATHERERS:
            assert f"## {a.section_title}\n" in contexts[synth]
            assert f"Body of {a.agent_id}." in contexts[synth]
    assert all(contexts[a.agent_id] is None for a in GATHERERS)


def test_metadata(contexts):
    meta = generate()["metadata"]
    assert meta["date"] == "2026-10-24"
    assert meta["title"] == "World Digest — October 24, 2026"
    assert meta["summary"] == "The day in brief."
    datetime.fromisoformat(meta["generatedAt"])


def test_sources_only_on_sections_that_have_them(contexts):
    sections = {s["id"]: s for s in generate()["sections"]}
    assert sections["political-news"]["sources"] == [{"title": "S", "url": "https://s.com"}]
    assert "sources" not in sections["daily-summary"]


def test_run_records_model_usage_and_prompt_versions(contexts):
    entry = generate()
    assert entry["model"] == "vendor/model"
    assert entry["usage"] == {"prompt_tokens": 700, "completion_tokens": 70, "cost": pytest.approx(0.07)}
    assert entry["promptVersions"] == {a.agent_id: a.version for a in AGENTS}


def test_a_failing_agent_omits_only_its_section(contexts, monkeypatch):
    ok = pipeline.run_agent

    async def flaky(agent, date, context=None, material=None):
        if agent.agent_id == "music-curator":
            raise RuntimeError("provider down")
        return await ok(agent, date, context, material)

    monkeypatch.setattr(pipeline, "run_agent", flaky)
    entry = generate()
    assert [s["id"] for s in entry["sections"]] == [i for i in SECTION_IDS if i != "music-releases"]
    assert "Music Releases" not in contexts["synthesis-agent"]
    pipeline.check_contract(entry)


def test_check_contract_rejects_a_broken_entry(contexts):
    entry = generate()
    del entry["metadata"]["summary"]
    with pytest.raises(ValueError):
        pipeline.check_contract(entry)


def test_a_leading_heading_repeating_the_section_title_is_dropped(contexts, monkeypatch):
    async def echo_title(agent, date, context=None, material=None):
        return AgentResult(f"### {agent.section_title}\n\n**Executive Summary:** Calm day.\n\nMore.")

    monkeypatch.setattr(pipeline, "run_agent", echo_title)
    entry = generate()
    outlook = next(s for s in entry["sections"] if s["id"] == "outlook")
    assert "<h3>Outlook</h3>" not in outlook["content"]
    assert entry["metadata"]["summary"] == "Calm day."



@pytest.mark.parametrize("status", [401, 402, 403])
def test_an_account_error_aborts_the_run_instead_of_dropping_sections(contexts, monkeypatch, account_error, status):
    # 2026-10-26: the key hit its daily cap mid-run and a 5-of-7 entry was written as if it were fine
    ok = pipeline.run_agent

    async def capped(agent, date, context=None, material=None):
        if not agent.gathers:
            raise account_error(status)
        return await ok(agent, date, context, material)

    monkeypatch.setattr(pipeline, "run_agent", capped)
    with pytest.raises(pipeline.AccountError):
        generate()


def test_gatherers_get_their_scraped_material(contexts):
    generate()
    for a in GATHERERS:
        assert contexts[a.agent_id, "material"].items[0].title == f"{a.agent_id} story"
    assert contexts["synthesis-agent", "material"] is None


def test_a_failed_scrape_omits_only_its_section(contexts, monkeypatch):
    scrape = pipeline.gather

    def flaky(agent, date):
        if agent.agent_id == "music-curator":
            raise RuntimeError("SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set")
        return scrape(agent, date)

    monkeypatch.setattr(pipeline, "gather", flaky)
    entry = generate()
    assert "music-releases" not in [s["id"] for s in entry["sections"]]
    assert len(entry["sections"]) == 6


def test_the_briefing_drops_links(contexts, monkeypatch):
    ok = pipeline.run_agent

    async def linked(agent, date, context=None, material=None):
        if agent.gathers:
            return AgentResult(f"Story [Outlet](https://news.example/{agent.agent_id}).")
        return await ok(agent, date, context, material)

    monkeypatch.setattr(pipeline, "run_agent", linked)
    generate()
    assert "Story Outlet." in contexts["synthesis-agent"]
    assert "https://" not in contexts["synthesis-agent"]
