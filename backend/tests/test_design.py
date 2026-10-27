import asyncio
import json
from types import SimpleNamespace as NS

import pytest

from diary import design, store
from diary.design import MAX_RETRIES, contrast, stories, validate

IDS = ["political-news", "financial-news", "outlook"]
LAYOUT = "/* layout: hero=split; political-news=banner/grid-2; financial-news=stat/grid-3; outlook=timeline/stack */"
TOKENS = """--paper: #f7f4ee; --paper-alt: #efeae0; --ink: #16140f; --ink-soft: #38342c;
  --muted: #5f5a4e; --accent: #a8321c; --accent-ink: #ffffff; --rule: #d9d2c3;
  --font-display: var(--ff-syne), sans-serif; --font-body: var(--ff-newsreader), serif;
  --font-ui: var(--ff-inter), sans-serif;"""
VALID = f"""/* theme: Quiet Ledger | Warm paper and a single rust accent for a day of slow, steady news. */
{LAYOUT}
.diary-page {{ {TOKENS} }}
.diary-page .diary-title, .diary-page .diary-section-title {{ letter-spacing: -0.02em; }}
@media (min-width: 1024px) {{ .diary-page .diary-hero {{ background: linear-gradient(180deg, #efeae0, #f7f4ee); }} }}
@container (min-width: 30rem) {{ .diary-page .diary-card-title {{ font-size: 1.5rem; }} }}
@keyframes rise {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
.diary-page .diary-section-title::before {{ content: "§ "; color: var(--accent); }}
"""
YESTERDAY = {"name": "Old Day", "note": "Yesterday's design.", "hero": "poster",
             "sections": {"outlook": {"card": "plain", "layout": "stack"}},
             "css": ".diary-page { --paper: #000000; --font-display: var(--ff-fraunces), serif; }"}


def test_a_good_design_passes():
    theme = validate(VALID, IDS)
    assert theme["name"] == "Quiet Ledger"
    assert theme["note"].startswith("Warm paper")
    assert theme["hero"] == "split"
    assert theme["sections"] == {"political-news": {"card": "banner", "layout": "grid-2"},
                                 "financial-news": {"card": "stat", "layout": "grid-3"},
                                 "outlook": {"card": "timeline", "layout": "stack"}}
    assert theme["css"] == VALID.strip()


def test_markdown_fences_are_unwrapped():
    assert validate(f"```css\n{VALID}\n```", IDS)["css"] == VALID.strip()


@pytest.mark.parametrize("css, reason", [
    (VALID + ".diary-title { color: red; }", "must start with .diary-page"),
    (VALID + ".diary-page .a, body { color: red; }", "must start with .diary-page"),
    (VALID + ".diary-pageant { color: red; }", "must start with .diary-page"),
    (VALID + '.diary-page { background: url("https://evil.example/x.png"); }', "resource"),
    (VALID + ".diary-page { background: image-set(a 1x); }", "resource"),
    (VALID + '@import "https://evil.example/a.css";', "@import"),
    (VALID + "@font-face { font-family: x; }", "@font-face"),
    (VALID + ".diary-page .diary-toc { position: fixed; }", "position: fixed"),
    (VALID + ".diary-page .diary-prose { display: none; }", "hides content"),
    (VALID + ".diary-page .diary-prose { visibility: hidden; }", "hides content"),
    (VALID + ".diary-page { color: red; } </style><script>", '"<"'),
    (VALID + '.diary-page { content: "\\75 rl"; }', "backslash"),
    (VALID.replace("/* theme: Quiet Ledger | ", "/* "), r"must start with /\* theme"),
    (VALID.replace(LAYOUT, ""), r"/\* layout"),
    (VALID.replace("--rule: #d9d2c3;", ""), "--rule"),
    (VALID.replace("#16140f", "black"), "6-digit hex"),
    (VALID.replace("--muted: #5f5a4e", "--muted: #c9c2b4"), "--muted on --paper"),
    (VALID + ".diary-page { color: red; } }", "parse error"),
    ("x" * 30001, "limit"),
    ("", "empty"),
])
def test_bad_stylesheets_are_rejected_with_the_reason(css, reason):
    with pytest.raises(ValueError, match=reason):
        validate(css, IDS)


@pytest.mark.parametrize("layout, reason", [
    ("hero=giant; political-news=banner/grid-2; financial-news=stat/grid-3; outlook=timeline/stack", "hero="),
    ("political-news=banner/grid-2; financial-news=stat/grid-3; outlook=timeline/stack", "hero="),
    ("hero=split; political-news=banner/grid-2; financial-news=stat/grid-3", "outlook"),
    ("hero=split; political-news=banner/grid-2; financial-news=stat/grid-3; outlook=timeline/stack; sports=tile/rail",
     "aren't on the page: sports"),
    ("hero=split; political-news=hexagon/grid-2; financial-news=stat/grid-3; outlook=timeline/stack", "hexagon"),
    ("hero=split; political-news=banner/spiral; financial-news=stat/grid-3; outlook=timeline/stack", "spiral"),
    ("hero=split; political-news=banner/grid-2; financial-news=banner/grid-3; outlook=stat/stack", "3 different card"),
    ("hero=split; political-news=banner/stack; financial-news=stat/stack; outlook=timeline/stack", "2 different layouts"),
    ("hero=split; political-news banner", "key=value"),
])
def test_bad_layout_picks_are_rejected_with_the_reason(layout, reason):
    with pytest.raises(ValueError, match=reason):
        validate(VALID.replace(LAYOUT, f"/* layout: {layout} */"), IDS)


def test_a_page_with_one_section_needs_no_variety():
    one = VALID.replace(LAYOUT, "/* layout: hero=classic; outlook=plain/stack */")
    assert validate(one, ["outlook"])["sections"] == {"outlook": {"card": "plain", "layout": "stack"}}


def test_today_must_differ_from_the_previous_day():
    assert validate(VALID, IDS, YESTERDAY)
    with pytest.raises(ValueError, match="hero=split"):
        validate(VALID, IDS, {**YESTERDAY, "hero": "split"})
    with pytest.raises(ValueError, match="--ff-syne"):
        validate(VALID, IDS, {**YESTERDAY, "css": ".diary-page { --font-display: var(--ff-syne), serif; }"})


def test_hiding_an_ornament_is_allowed():
    assert validate(VALID + ".diary-page .diary-prose ul > li::before { display: none; }", IDS)


def test_hiding_content_next_to_an_ornament_is_not():
    with pytest.raises(ValueError, match="hides content"):
        validate(VALID + ".diary-page li::before, .diary-page .diary-prose { display: none; }", IDS)


def test_a_dark_mode_variant_is_checked_too():
    dark = '@media (prefers-color-scheme: dark) { .diary-page { --paper: #151412; --accent: #e74c3c; } }'
    # 2026-10-25: white on #e74c3c is 3.8:1, and passed while only the top-level tokens were checked
    with pytest.raises(ValueError, match="inside @media"):
        validate(VALID + dark, IDS)


def test_header_colours_are_checked_on_paper_alt():
    with pytest.raises(ValueError, match="--accent on --paper-alt"):
        validate(VALID.replace("--paper-alt: #efeae0", "--paper-alt: #d8cfbd"), IDS)


def test_a_universal_selector_cannot_set_colours():
    with pytest.raises(ValueError, match="outranks"):
        validate(VALID + '.diary-page[data-hero="poster"] .diary-hero * { color: var(--accent-ink); }', IDS)
    assert validate(VALID + ".diary-page .diary-hero * { letter-spacing: 0.01em; }", IDS)


def test_tokens_can_only_be_set_on_the_page():
    with pytest.raises(ValueError, match="only be set in a .diary-page rule"):
        validate(VALID + '.diary-page[data-hero="poster"] .diary-hero { --accent: #ffffff; }', IDS)


@pytest.mark.parametrize("extra, ok", [
    (".diary-page .diary-spark-change { color: #1d6b3e; }", True),   # fine on light paper
    (".diary-page .diary-spark-change { color: #c9c2b4; }", False),  # too pale
    (".diary-page .x { color: #c9c2b4; background: #111111; }", True),  # own background: not ours to judge
    (".diary-page .x { color: var(--ink); }", True),
    (".diary-page .x { color: currentColor; }", True),
])
def test_literal_text_colours_are_checked(extra, ok):
    if ok:
        assert validate(VALID + extra, IDS)
    else:
        with pytest.raises(ValueError, match="sets color #c9c2b4"):
            validate(VALID + extra, IDS)


def test_a_literal_colour_must_also_work_in_dark_mode():
    dark = ("@media (prefers-color-scheme: dark) { .diary-page { --paper: #121110; --paper-alt: #1b1916; "
            "--ink: #f4f0e7; --ink-soft: #d6d0c3; --muted: #a29b8c; --accent: #f08a6c; --accent-ink: #1a0d08; } }")
    green = ".diary-page .diary-spark-change { color: #1d6b3e; }"
    # 2026-10-25: readable on light paper, 2.9:1 in dark mode
    with pytest.raises(ValueError, match="inside @media"):
        validate(VALID + dark + green, IDS)
    custom = (".diary-page { --up: #1d6b3e; } @media (prefers-color-scheme: dark) { .diary-page { --up: #7fd19b; } } "
              ".diary-page .diary-spark-change { color: var(--up); }")
    assert validate(VALID + dark + custom, IDS)


def test_tokens_inside_media_queries_do_not_count():
    css = VALID.replace(f".diary-page {{ {TOKENS} }}", f"@media (min-width: 1px) {{ .diary-page {{ {TOKENS} }} }}")
    with pytest.raises(ValueError, match="must set"):
        validate(css, IDS)


def test_contrast_matches_wcag():
    assert contrast("#000000", "#ffffff") == pytest.approx(21)
    assert contrast("#777777", "#ffffff") == pytest.approx(4.48, abs=0.01)


def test_story_counts_match_the_cards_the_page_renders():
    assert stories("### A\n\ntext\n\n### B\n\nmore") == 2
    assert stories("Intro.\n\n### A\n\ntext") == 2
    assert stories("Just one paragraph.") == 1


def test_the_prompt_quotes_the_base_stylesheet_and_every_component():
    p = design.prompt()
    assert ".diary-theme-name {" in p and "--paper: #f7f4ee;" in p and "diary:end" not in p
    assert all(f"- {name}:" in p for name in [*design.HEROES, *design.CARDS, *design.LAYOUTS])
    assert all(f"var({font})" in p for font in design.FONTS)


def test_recent_designs_come_from_the_store_newest_first(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    for day, theme in [("2026-10-20", YESTERDAY), ("2026-10-21", None), ("2026-10-22", {**YESTERDAY, "name": "B"}),
                       ("2026-10-26", {**YESTERDAY, "name": "Today"})]:
        entry = {"metadata": {"date": day}, "sections": []} | ({"theme": theme} if theme else {})
        (tmp_path / f"{day}.json").write_text(json.dumps(entry))
    assert [(d, t["name"]) for d, t in design.recent("2026-10-26")] == [("2026-10-22", "B"), ("2026-10-20", "Old Day")]


class FakeCompletions:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        content, finish = reply if isinstance(reply, tuple) else (reply, "stop")
        usage = NS(model_dump=lambda: {"prompt_tokens": 100, "completion_tokens": 50, "cost": 0.01,
                                       "prompt_tokens_details": {"cached_tokens": 0}})
        return NS(choices=[NS(message=NS(content=content), finish_reason=finish)], usage=usage)


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setattr(design, "recent", lambda date: [("2026-10-25", YESTERDAY)])

    def install(*replies):
        completions = FakeCompletions(replies)
        monkeypatch.setattr(design, "client", lambda: NS(chat=NS(completions=completions)))
        monkeypatch.setenv("OPENROUTER_MODEL", "vendor/model")
        return completions
    return install


SECTIONS = [("political-news", "Political News", "### Europe\n\nVoters went to the polls.\n\n### Asia\n\nCalm."),
            ("financial-news", "Financial News", "Stocks rose 2%."),
            ("outlook", "Outlook", "- Results due Tuesday")]


def run():
    return asyncio.run(design.run_design("2026-10-26", "World Digest — October 26, 2026",
                                         "A tense election day.", SECTIONS))


def test_the_model_gets_the_whole_edition_and_recent_designs(fake):
    calls = fake(VALID)
    theme, usage = run()
    assert theme["name"] == "Quiet Ledger"
    assert usage == {"prompt_tokens": 100, "completion_tokens": 50, "cost": 0.01}
    system, user = (m["content"] for m in calls.calls[0]["messages"])
    assert system == design.prompt()
    assert "Monday, October 26, 2026" in user and "A tense election day." in user
    assert "- political-news: Political News, 2 stories" in user and "- outlook: Outlook, 1 story" in user
    assert '2026-10-25 "Old Day": Yesterday\'s design. | header poster | --paper #000000' in user
    assert "--font-display --ff-fraunces" in user and "outlook=plain/stack" in user
    assert "## Political News\n\n### Europe\n\nVoters went to the polls." in user
    assert calls.calls[0]["extra_body"] == {"reasoning": {"enabled": False}}


def test_a_rejected_design_is_retried_with_the_reason(fake):
    calls = fake(".diary-title { color: red; }", VALID)
    theme, usage = run()
    assert theme["name"] == "Quiet Ledger"
    retry = calls.calls[1]["messages"]
    assert retry[-2] == {"role": "assistant", "content": ".diary-title { color: red; }"}
    assert "rejected" in retry[-1]["content"] and "/* theme:" in retry[-1]["content"]
    assert usage["cost"] == pytest.approx(0.02)


def test_repeating_yesterday_is_retried(fake):
    calls = fake(VALID.replace("hero=split", "hero=poster"), VALID)
    assert run()[0]["hero"] == "split"
    assert "previous day also used hero=poster" in calls.calls[1]["messages"][-1]["content"]


def test_gives_up_after_five_retries(fake):
    calls = fake(*["nope"] * (1 + MAX_RETRIES))
    assert run() == (None, {"prompt_tokens": 600, "completion_tokens": 300, "cost": pytest.approx(0.06)})
    assert len(calls.calls) == 1 + MAX_RETRIES


def test_a_truncated_stylesheet_is_retried(fake):
    calls = fake((VALID, "length"), VALID)
    assert run()[0]["name"] == "Quiet Ledger"
    assert "cut off" in calls.calls[1]["messages"][-1]["content"]


def test_provider_errors_are_retried_and_a_rejected_key_stops(fake, account_error):
    calls = fake(account_error(500), VALID)
    assert run()[0]["name"] == "Quiet Ledger"
    assert len(calls.calls) == 2

    calls = fake(account_error(402), VALID)
    assert run() == (None, {})
    assert len(calls.calls) == 1
