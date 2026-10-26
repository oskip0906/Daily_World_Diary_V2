import asyncio
from datetime import datetime

import pytest

from diary import pipeline
from diary.agent import AgentResult
from diary.prompts import AGENTS

SEARCHERS = [a for a in AGENTS if a.searches]
SECTION_IDS = ["political-news", "financial-news", "entertainment-news", "music-releases",
               "stock-analysis", "daily-summary", "outlook"]


@pytest.fixture
def contexts(monkeypatch):
    """Stub every agent; record the context each one was given."""
    seen = {}

    async def fake_run_agent(agent, date, context=None):
        seen[agent.agent_id] = context
        if agent.agent_id == "synthesis-agent":
            md = "### Executive Summary\n\nThe day in **brief**.\n\nMore detail."
        else:
            md = f"### {agent.agent_name}\n\nBody of {agent.agent_id}."
        sources = [{"title": "S", "url": "https://s.com"}] if agent.searches else []
        return AgentResult(md, sources, {"prompt_tokens": 100, "completion_tokens": 10, "cost": 0.01})

    monkeypatch.setattr(pipeline, "run_agent", fake_run_agent)
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


def test_synthesisers_receive_all_five_searcher_sections(contexts):
    generate()
    for synth in ("synthesis-agent", "outlook-agent"):
        for a in SEARCHERS:
            assert f"## {a.section_title}\n" in contexts[synth]
            assert f"Body of {a.agent_id}." in contexts[synth]
    assert all(contexts[a.agent_id] is None for a in SEARCHERS)


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

    async def flaky(agent, date, context=None):
        if agent.agent_id == "music-curator":
            raise RuntimeError("provider down")
        return await ok(agent, date, context)

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


def test_prompts_payload_matches_the_prompts_response_type():
    payload = pipeline.prompts_payload()
    assert payload["meta"] == {"totalAgents": 7, "schemaVersion": "1.0.0"}
    first = payload["prompts"][0]
    assert set(first) == {"agentId", "agentName", "description", "systemPrompt", "version", "lastUpdated"}
    assert first["agentId"] == "political-analyst"


def test_a_leading_heading_repeating_the_section_title_is_dropped(contexts, monkeypatch):
    async def echo_title(agent, date, context=None):
        return AgentResult(f"### {agent.section_title}\n\n**Executive Summary:** Calm day.\n\nMore.")

    monkeypatch.setattr(pipeline, "run_agent", echo_title)
    entry = generate()
    outlook = next(s for s in entry["sections"] if s["id"] == "outlook")
    assert "<h3>Outlook</h3>" not in outlook["content"]
    assert entry["metadata"]["summary"] == "Calm day."
