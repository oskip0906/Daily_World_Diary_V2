import asyncio
from datetime import datetime

import pytest

from diary import pipeline
from diary.agent import AgentResult
from diary.prompts import AGENTS
from diary.sources import Item, Material

GATHERERS = [a for a in AGENTS if a.gathers]
SECTION_IDS = ["political-news", "financial-news", "entertainment-news", "music-releases",
               "stock-analysis", "outlook"]
THREAD = {"id": "serbia-protests", "title": "Serbia's protests", "story": "political-news/1", "day": 2,
          "follows": ["2026-10-23/political-news/2"]}
THEME = {"name": "Night Shift", "note": "A dark, tense edition.", "hero": "poster",
         "sections": {"outlook": {"card": "plain", "layout": "stack"}}, "css": ".diary-page { --paper: #000000; }"}


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
        return AgentResult(md, {"prompt_tokens": 100, "completion_tokens": 10, "cost": 0.01})

    async def fake_design(date, title, summary, sections):
        seen["design"] = (date, title, summary, sections)
        return THEME, {"prompt_tokens": 50, "completion_tokens": 5, "cost": 0.005}

    monkeypatch.setattr(pipeline, "run_agent", fake_run_agent)
    async def fake_threads(entry):
        seen["threads"] = entry
        return [THREAD], {"prompt_tokens": 20, "completion_tokens": 2, "cost": 0.001}

    monkeypatch.setattr(pipeline, "run_design", fake_design)
    monkeypatch.setattr(pipeline, "run_threads", fake_threads)
    monkeypatch.setattr(pipeline, "gather", lambda agent, date: Material(
        [Item(f"{agent.agent_id} story", f"https://news.example/{agent.agent_id}", "Outlet")]))
    monkeypatch.setenv("OPENROUTER_MODEL", "vendor/model")
    return seen


def generate(date="2026-10-24"):
    return asyncio.run(pipeline.generate(date))


def test_sections_match_the_frontend_contract(contexts):
    entry = generate()
    assert [s["id"] for s in entry["sections"]] == SECTION_IDS
    assert [s["order"] for s in entry["sections"]] == [1, 2, 3, 4, 5, 7]
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


def test_charts_ride_along_with_their_section(contexts, monkeypatch):
    ok = pipeline.run_agent
    chart = {"group": "Indices", "label": "S&P 500", "symbol": "^GSPC", "change": 0.3, "closes": [1.0, 2.0]}

    async def charted(agent, date, context=None, material=None):
        result = await ok(agent, date, context, material)
        if agent.agent_id == "stock-analyst":
            result.charts = [chart]
        return result

    monkeypatch.setattr(pipeline, "run_agent", charted)
    entry = generate()
    sections = {s["id"]: s for s in entry["sections"]}
    assert sections["stock-analysis"]["charts"] == [chart]
    assert "charts" not in sections["political-news"]
    pipeline.check_contract(entry)


@pytest.mark.parametrize("md, expected", [
    ("### Executive Summary\n\nThe day in **brief**.", "The day in brief."),
    ("### Markets fell as talks stalled.", "Markets fell as talks stalled."),  # 2026-10-26
    ("", ""),
])
def test_summary_takes_the_first_paragraph_or_a_lone_heading(md, expected):
    assert pipeline.summary(md) == expected


def test_the_summary_is_metadata_not_a_section(contexts):
    entry = generate()
    assert "daily-summary" not in [s["id"] for s in entry["sections"]]
    assert entry["metadata"]["summary"] == "The day in brief."
    assert all("sources" not in s for s in entry["sections"])


def test_the_designer_reads_the_finished_page(contexts):
    entry = generate()
    date, title, summary, sections = contexts["design"]
    assert (date, title, summary) == ("2026-10-24", "World Digest — October 24, 2026", "The day in brief.")
    assert [sid for sid, _, _ in sections] == SECTION_IDS
    assert sections[0][1] == "Political News" and "Body of political-analyst." in sections[0][2]
    assert entry["theme"] == THEME
    pipeline.check_contract(entry)


def test_threads_link_the_assembled_entry(contexts):
    entry = generate()
    assert contexts["threads"]["sections"] == entry["sections"]  # it sees the rendered page
    assert entry["threads"] == [THREAD]
    pipeline.check_contract(entry)


def test_a_crashing_threads_step_still_writes_the_entry(contexts, monkeypatch):
    async def boom(entry):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(pipeline, "run_threads", boom)
    entry = generate()
    assert "threads" not in entry and len(entry["sections"]) == 6


def test_no_theme_when_the_designer_gives_up(contexts, monkeypatch):
    async def gave_up(*args):
        return None, {"cost": 0.02}

    monkeypatch.setattr(pipeline, "run_design", gave_up)
    entry = generate()
    assert "theme" not in entry
    assert len(entry["sections"]) == 6


def test_a_crashing_designer_still_writes_the_entry(contexts, monkeypatch):
    async def boom(*args):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(pipeline, "run_design", boom)
    entry = generate()
    assert "theme" not in entry and len(entry["sections"]) == 6


def test_run_records_model_usage_and_prompt_versions(contexts):
    entry = generate()
    assert entry["model"] == "vendor/model"
    # seven agents, the designer and the threads step
    assert entry["usage"] == {"prompt_tokens": 770, "completion_tokens": 77, "cost": pytest.approx(0.076)}
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
    assert len(entry["sections"]) == 5


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


def test_a_redesign_reads_the_stories_back_from_the_stored_html():
    entry = {"metadata": {"date": "2026-10-24", "title": "T", "summary": "S"},
             "sections": [{"id": "outlook", "title": "Outlook", "order": 7, "content": "<ul><li>Fed on Wednesday</li></ul>"},
                          {"id": "political-news", "title": "Political News", "order": 1,
                           "content": '<p>Lead.</p>\n<h3>One</h3>\n<p>Text <a href="https://x.example">Reuters</a>.</p>'
                                      "\n<h3>Two</h3>\n<p>More.</p>"}]}
    seen = []

    async def design(*args):
        seen.append(args)
        return None, {}

    asyncio.run(pipeline.redesign(entry, design))
    # one ### per card, as the page splits them, in page order, citations dropped
    assert seen == [("2026-10-24", "T", "S", [("political-news", "Political News", "Lead.\n\n### One\n\nText.\n\n### Two\n\nMore."),
                                              ("outlook", "Outlook", "Fed on Wednesday")])]
