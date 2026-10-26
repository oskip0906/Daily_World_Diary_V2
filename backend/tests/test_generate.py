import json

import pytest

from diary import generate, pipeline, store
from diary.agent import AgentResult


@pytest.fixture
def calls(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    monkeypatch.setenv("OPENROUTER_MODEL", "vendor/model")
    made = []

    async def fake_run_agent(agent, date, context=None):
        made.append(agent.agent_id)
        return AgentResult(f"Body of {agent.agent_id}.")

    monkeypatch.setattr(pipeline, "run_agent", fake_run_agent)
    return made


def test_writes_the_entry_and_prompts(calls, tmp_path):
    assert generate.main(["--date", "2026-10-24"]) == 0
    assert store.read("2026-10-24")["metadata"]["date"] == "2026-10-24"
    assert json.loads((tmp_path / "prompts.json").read_text())["meta"]["totalAgents"] == 7


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
    async def down(agent, date, context=None):
        raise RuntimeError("everything is down")

    monkeypatch.setattr(pipeline, "run_agent", down)
    assert generate.main(["--date", "2026-10-24"]) == 1
    assert store.read("2026-10-24") is None


def test_bad_date_is_rejected(calls):
    with pytest.raises(SystemExit):
        generate.main(["--date", "yesterday"])
