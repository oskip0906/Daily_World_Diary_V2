import asyncio
import json
from types import SimpleNamespace as NS

import pytest

from diary import store, threads
from diary.threads import split, stories, validate

POLITICS = ('<p>Intro text.</p>\n<h3>Serbia</h3>\n<p>Students marched <a href="https://n.example/1">NBC</a>.</p>'
            "\n<h3>Brazil</h3>\n<p>The runoff tightened.</p>")


def entry(date, content=POLITICS, thread_list=None):
    e = {"metadata": {"date": date}, "sections": [
        {"id": "political-news", "title": "Political News", "content": content, "order": 1},
        {"id": "stock-analysis", "title": "Stock Analysis", "content": "<h3>Indices</h3><p>Up.</p>", "order": 5},
        {"id": "daily-summary", "title": "Daily Summary", "content": "<p>Old summary.</p>", "order": 6}]}
    return e | ({"threads": thread_list} if thread_list else {})


def test_split_mirrors_the_page_cards():
    assert split(POLITICS) == [(None, "<p>Intro text.</p>"), ("Serbia", '<p>Students marched <a href="https://n.example/1">NBC</a>.</p>'),
                               ("Brazil", "<p>The runoff tightened.</p>")]


def test_stories_are_refs_with_plain_text_from_news_sections_only():
    assert stories(entry("2026-10-24")) == {"political-news/1": "Political News: Intro text.",
                                            "political-news/2": "Serbia: Students marched.",
                                            "political-news/3": "Brazil: The runoff tightened."}


@pytest.fixture
def week(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)

    def write(e):
        (tmp_path / f"{e['metadata']['date']}.json").write_text(json.dumps(e))
    write(entry("2026-10-10"))  # outside the 7-day window
    for d in ("2026-10-20", "2026-10-21", "2026-10-22", "2026-10-23", "2026-10-24", "2026-10-25"):
        write(entry(d))
    write(entry("2026-10-26", thread_list=[{"id": "serbia-protests", "title": "Serbia's protests",
                                            "story": "political-news/2", "day": 2,
                                            "follows": ["2026-10-25/political-news/2"]}]))
    return tmp_path


def test_history_marks_thread_members_and_keeps_only_the_past_week(week):
    past, known = threads.history("2026-10-27")
    assert "2026-10-10/political-news/1" not in past
    assert len(past) == 7 * 3  # the 7 entries before today (20th-26th), 3 stories each
    assert past["2026-10-26/political-news/2"] == "[thread serbia-protests: Serbia's protests] Serbia: Students marched."
    assert past["2026-10-25/political-news/2"].startswith("[thread serbia-protests")
    assert known == {"serbia-protests": {"title": "Serbia's protests",
                                         "members": ["2026-10-25/political-news/2", "2026-10-26/political-news/2"]}}


TODAY = {"political-news/1": "Serbia: More marches.", "political-news/2": "Brazil: Results."}


def check(picks, past_and_known=None):
    past, known = past_and_known or ({"2026-10-25/political-news/2": "Serbia", "2026-10-24/political-news/3": "Brazil",
                                      "2026-10-26/political-news/2": "[thread serbia-protests] Serbia"},
                                     {"serbia-protests": {"title": "Serbia's protests",
                                                          "members": ["2026-10-22/political-news/1",
                                                                      "2026-10-26/political-news/2"]}})
    return validate(json.dumps({"threads": picks}), TODAY, past, known)


def test_continuing_a_thread_inherits_its_members_and_counts_days():
    [t] = check([{"story": "political-news/1", "id": "serbia-protests", "title": "Serbia's protests", "follows": []}])
    assert t == {"id": "serbia-protests", "title": "Serbia's protests", "story": "political-news/1", "day": 3,
                 "follows": ["2026-10-22/political-news/1", "2026-10-26/political-news/2"]}


def test_a_new_thread_counts_the_days_it_follows():
    [t] = check([{"story": "political-news/2", "id": "brazil-runoff", "title": "Brazil's runoff",
                  "follows": ["2026-10-24/political-news/3"]}])
    assert t["day"] == 2 and t["follows"] == ["2026-10-24/political-news/3"]


def test_inconsistent_picks_are_repaired_or_dropped_not_rejected():
    known = {"serbia-protests": {"title": "Serbia's protests", "members": ["2026-10-26/political-news/2"]}}
    past = {"2026-10-24/political-news/3": "Brazil", "2026-10-26/political-news/2": "Serbia"}
    raw = json.dumps({"threads": [
        # a new id following an existing thread's story joins that thread
        {"story": "political-news/1", "id": "serbia-two", "title": "Serbia again", "follows": ["2026-10-26/political-news/2"]},
        # a story's second thread is ignored
        {"story": "political-news/1", "id": "x-y", "title": "Other thing", "follows": ["2026-10-24/political-news/3"]},
        # a new thread that follows nothing is dropped
        {"story": "political-news/2", "id": "brazil", "title": "Brazil's runoff", "follows": []}]})
    assert [(t["story"], t["id"], t["title"]) for t in validate(raw, TODAY, past, known)] == \
        [("political-news/1", "serbia-protests", "Serbia's protests")]


def test_markdown_fences_and_empty_replies_are_fine():
    assert validate('```json\n{"threads": []}\n```', TODAY, {}, {}) == []


@pytest.mark.parametrize("picks, reason", [
    ("not json", "JSON"),
    ({"threads": "x"}, "must be a list"),
    ([{"story": "sports/1", "id": "a-b", "title": "A thing", "follows": ["2026-10-24/political-news/3"]}], "not one of today's"),
    ([{"story": "political-news/2", "id": "Brazil Runoff", "title": "Brazil", "follows": ["2026-10-24/political-news/3"]}], "slug"),
    ([{"story": "political-news/2", "id": "brazil", "title": "B", "follows": ["2026-10-24/political-news/3"]}], "3-60"),
    ([{"story": "political-news/2", "id": "brazil", "title": "Brazil's runoff", "follows": ["2026-09-01/x/1"]}], "aren't in"),
])
def test_bad_links_are_rejected_with_the_reason(picks, reason):
    raw = picks if isinstance(picks, str) else json.dumps(picks if isinstance(picks, dict) else {"threads": picks})
    with pytest.raises(ValueError, match=reason):
        validate(raw, TODAY, {"2026-10-24/political-news/3": "Brazil", "2026-10-26/political-news/2": "Serbia"},
                 {"serbia-protests": {"title": "S", "members": ["2026-10-26/political-news/2"]}})


class FakeCompletions:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        usage = NS(model_dump=lambda: {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.001})
        return NS(choices=[NS(message=NS(content=reply), finish_reason="stop")], usage=usage)


@pytest.fixture
def fake(week, monkeypatch):
    def install(*replies):
        completions = FakeCompletions(replies)
        monkeypatch.setattr(threads, "client", lambda: NS(chat=NS(completions=completions)))
        monkeypatch.setenv("OPENROUTER_MODEL", "vendor/model")
        return completions
    return install


GOOD = json.dumps({"threads": [{"story": "political-news/2", "id": "serbia-protests", "title": "Serbia's protests",
                                "follows": []}]})


def run():
    return asyncio.run(threads.run_threads(entry("2026-10-27")))


def test_run_links_today_with_the_week(fake):
    calls = fake(GOOD)
    linked, usage = run()
    assert linked[0]["day"] == 3 and linked[0]["story"] == "political-news/2"
    assert usage == {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.001}
    system, user = (m["content"] for m in calls.calls[0]["messages"])
    assert system == threads.PROMPT
    assert "- political-news/2 Serbia: Students marched." in user
    assert "- 2026-10-26/political-news/2 [thread serbia-protests: Serbia's protests] Serbia" in user


def test_a_rejected_reply_is_retried_with_the_reason_then_given_up(fake):
    calls = fake("nope", GOOD)
    assert run()[0][0]["id"] == "serbia-protests"
    assert "rejected" in calls.calls[1]["messages"][-1]["content"]

    calls = fake(*["nope"] * (1 + threads.MAX_RETRIES))
    assert run()[0] == []
    assert len(calls.calls) == 1 + threads.MAX_RETRIES


def test_a_rejected_key_stops_at_once(fake, account_error):
    calls = fake(account_error(402), GOOD)
    assert run() == ([], {})
    assert len(calls.calls) == 1


def test_no_call_without_a_past_week(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(threads, "client", lambda: pytest.fail("called the model"))
    assert run() == ([], {})
