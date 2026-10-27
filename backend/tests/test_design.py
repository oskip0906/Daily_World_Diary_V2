import asyncio
from types import SimpleNamespace as NS

import pytest

from diary import design
from diary.design import MAX_RETRIES, contrast, validate

TOKENS = """--paper: #f7f4ee; --paper-alt: #efeae0; --ink: #16140f; --ink-soft: #38342c;
  --muted: #5f5a4e; --accent: #a8321c; --accent-ink: #ffffff; --rule: #d9d2c3;
  --font-display: var(--ff-fraunces), serif; --font-body: var(--ff-newsreader), serif;
  --font-ui: var(--ff-inter), sans-serif;"""
VALID = f"""/* theme: Quiet Ledger | Warm paper and a single rust accent for a day of slow, steady news. */
.diary-page {{ {TOKENS} }}
.diary-page .diary-title, .diary-page .diary-section-title {{ letter-spacing: -0.02em; }}
@media (min-width: 1024px) {{ .diary-page .diary-hero {{ background: linear-gradient(180deg, #efeae0, #f7f4ee); }} }}
@keyframes rise {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
.diary-page .diary-section-title::before {{ content: "§ "; color: var(--accent); }}
"""


def test_a_good_stylesheet_passes():
    theme = validate(VALID)
    assert theme["name"] == "Quiet Ledger"
    assert theme["note"].startswith("Warm paper")
    assert theme["css"] == VALID.strip()


def test_markdown_fences_are_unwrapped():
    assert validate(f"```css\n{VALID}\n```")["css"] == VALID.strip()


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
    (VALID.replace("--rule: #d9d2c3;", ""), "--rule"),
    (VALID.replace("#16140f", "black"), "6-digit hex"),
    (VALID.replace("--muted: #5f5a4e", "--muted: #c9c2b4"), "--muted on --paper"),
    (VALID + ".diary-page { color: red; } }", "parse error"),
    ("x" * 20001, "limit"),
    ("", "empty"),
])
def test_bad_stylesheets_are_rejected_with_the_reason(css, reason):
    with pytest.raises(ValueError, match=reason):
        validate(css)


def test_hiding_an_ornament_is_allowed():
    assert validate(VALID + ".diary-page .diary-prose ul > li::before { display: none; }")


def test_hiding_content_next_to_an_ornament_is_not():
    with pytest.raises(ValueError, match="hides content"):
        validate(VALID + ".diary-page li::before, .diary-page .diary-prose { display: none; }")


def test_a_dark_mode_variant_is_checked_too():
    dark = '@media (prefers-color-scheme: dark) { .diary-page { --paper: #151412; --accent: #e74c3c; } }'
    # 2026-10-25: white on #e74c3c is 3.8:1, and passed while only the top-level tokens were checked
    with pytest.raises(ValueError, match="inside @media"):
        validate(VALID + dark)


def test_header_colours_are_checked_on_paper_alt():
    with pytest.raises(ValueError, match="--accent on --paper-alt"):
        validate(VALID.replace("--paper-alt: #efeae0", "--paper-alt: #d8cfbd"))


def test_tokens_inside_media_queries_do_not_count():
    css = VALID.replace(f".diary-page {{ {TOKENS} }}", f"@media (min-width: 1px) {{ .diary-page {{ {TOKENS} }} }}")
    with pytest.raises(ValueError, match="must set"):
        validate(css)


def test_contrast_matches_wcag():
    assert contrast("#000000", "#ffffff") == pytest.approx(21)
    assert contrast("#777777", "#ffffff") == pytest.approx(4.48, abs=0.01)


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
    def install(*replies):
        completions = FakeCompletions(replies)
        monkeypatch.setattr(design, "client", lambda: NS(chat=NS(completions=completions)))
        monkeypatch.setenv("OPENROUTER_MODEL", "vendor/model")
        return completions
    return install


SECTIONS = [("political-news", "Political News", "### Europe\n\nVoters went to the polls."),
            ("outlook", "Outlook", "- Results due Tuesday")]


def run():
    return asyncio.run(design.run_design("2026-10-26", "World Digest — October 26, 2026",
                                         "A tense election day.", SECTIONS))


def test_the_model_gets_the_whole_edition(fake):
    calls = fake(VALID)
    theme, usage = run()
    assert theme["name"] == "Quiet Ledger"
    assert usage == {"prompt_tokens": 100, "completion_tokens": 50, "cost": 0.01}
    system, user = (m["content"] for m in calls.calls[0]["messages"])
    assert system == design.prompt()
    assert ".diary-theme-name {" in system and "--paper: #f7f4ee;" in system  # the base stylesheet
    assert "diary:end" not in system
    assert "Monday, October 26, 2026" in user and "A tense election day." in user
    assert '- Political News (data-section="political-news")' in user
    assert "## Political News\n\n### Europe\n\nVoters went to the polls." in user
    assert calls.calls[0]["extra_body"] == {"reasoning": {"enabled": False}}


def test_a_rejected_stylesheet_is_retried_with_the_reason(fake):
    calls = fake(".diary-title { color: red; }", VALID)
    theme, usage = run()
    assert theme["name"] == "Quiet Ledger"
    retry = calls.calls[1]["messages"]
    assert retry[-2] == {"role": "assistant", "content": ".diary-title { color: red; }"}
    assert "rejected" in retry[-1]["content"] and "/* theme:" in retry[-1]["content"]
    assert usage["cost"] == pytest.approx(0.02)


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
