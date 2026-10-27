import asyncio

import pytest

from diary import generate, pipeline, store
from diary.agent import AgentResult
from diary.sources import Material


@pytest.fixture
def calls(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    monkeypatch.setenv("OPENROUTER_MODEL", "vendor/model")
    made = []

    async def fake_run_agent(agent, date, context=None, material=None):
        made.append(agent.agent_id)
        return AgentResult(f"Body of {agent.agent_id}.")

    async def no_design(*args):
        made.append("design")
        return None, {}

    monkeypatch.setattr(pipeline, "run_agent", fake_run_agent)
    async def no_threads(entry):
        return [], {}

    monkeypatch.setattr(pipeline, "run_design", no_design)
    monkeypatch.setattr(pipeline, "run_threads", no_threads)
    monkeypatch.setattr(pipeline, "gather", lambda agent, date: Material([]))
    return made


def test_writes_the_entry(calls, tmp_path):
    assert generate.main(["--date", "2026-10-24"]) == 0
    assert store.read("2026-10-24")["metadata"]["date"] == "2026-10-24"
    assert [p.name for p in tmp_path.iterdir()] == ["2026-10-24.json"]


def test_existing_date_is_refused_before_any_model_call(calls):
    generate.main(["--date", "2026-10-24"])
    calls.clear()
    assert generate.main(["--date", "2026-10-24"]) == 1
    assert calls == []


def test_force_regenerates(calls):
    generate.main(["--date", "2026-10-24"])
    assert generate.main(["--date", "2026-10-24", "--force"]) == 0


def test_dry_run_uses_stub_text_and_writes_nothing(calls, tmp_path):
    assert generate.main(["--date", "2026-10-24", "--dry-run"]) == 0
    assert calls == []
    assert list(tmp_path.iterdir()) == []


def test_an_entry_with_no_sections_is_not_written(calls, monkeypatch):
    async def down(agent, date, context=None, material=None):
        raise RuntimeError("everything is down")

    monkeypatch.setattr(pipeline, "run_agent", down)
    assert generate.main(["--date", "2026-10-24"]) == 1
    assert store.read("2026-10-24") is None


def test_bad_date_is_rejected(calls):
    with pytest.raises(SystemExit):
        generate.main(["--date", "yesterday"])


def test_an_account_error_writes_nothing_and_fails(calls, monkeypatch, account_error):
    # the 2026-10-26 shape: searchers succeed, then the key's spend cap rejects the synthesisers
    async def capped(agent, date, context=None, material=None):
        if not agent.gathers:
            raise account_error(403)
        return AgentResult(f"Body of {agent.agent_id}.")

    monkeypatch.setattr(pipeline, "run_agent", capped)
    assert generate.main(["--date", "2026-10-24"]) == 1
    assert store.read("2026-10-24") is None


def test_redesign_replaces_only_the_theme(calls, monkeypatch):
    generate.main(["--date", "2026-10-24"])
    before = store.read("2026-10-24")

    async def design(date, title, summary, sections):
        return {"name": "New Look", "note": "A redesign.", "mood": "bad", "hero": "poster", "sections": {},
                "css": ".diary-page {}"}, {"cost": 0.01}

    monkeypatch.setattr(pipeline, "run_design", design)
    assert generate.main(["--redesign"]) == 0
    after = store.read("2026-10-24")
    assert after["theme"]["name"] == "New Look"
    assert after["sections"] == before["sections"] and after["metadata"] == before["metadata"]
    assert after["usage"]["cost"] == pytest.approx(before["usage"]["cost"] + 0.01)


def test_a_failed_redesign_leaves_the_entry_as_it_was(calls):
    generate.main(["--date", "2026-10-24"])
    before = store.read("2026-10-24")
    # 10-24's design fails (the fixture's designer returns none); 10-25 has no entry
    assert generate.main(["--redesign", "2026-10-24", "2026-10-25"]) == 1
    assert store.read("2026-10-24") == before
    assert store.read("2026-10-25") is None


def test_redesign_runs_every_day_in_one_event_loop(calls, monkeypatch):
    # 2026-10-27: a loop per day broke the cached OpenRouter client from the second day on
    # ("Event loop is closed"), so only the first day was redesigned
    for date in ("2026-10-23", "2026-10-24"):
        generate.main(["--date", date])
    loops = []

    async def design(date, title, summary, sections):
        loops.append(asyncio.get_running_loop())
        return None, {}

    monkeypatch.setattr(pipeline, "run_design", design)
    generate.main(["--redesign"])
    assert len(loops) == 2 and loops[0] is loops[1]
