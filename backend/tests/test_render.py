from diary.render import render, to_text


def test_markdown_becomes_html():
    html = render("### Markets\n\nStocks **rose**.\n\n- one\n- two")
    assert "<h3>Markets</h3>" in html
    assert "<strong>rose</strong>" in html
    assert "<li>one</li>" in html


def test_script_tags_are_removed():
    assert "<script" not in render("hi <script>alert(1)</script>")


def test_event_handlers_are_removed():
    html = render('<img src=x onerror="alert(1)">')
    assert "onerror" not in html


def test_javascript_links_are_removed():
    html = render("[click](javascript:alert(1))")
    assert "javascript:" not in html


def test_http_links_survive():
    assert 'href="https://example.com"' in render("[ok](https://example.com)")


def test_top_level_headings_are_demoted_to_h3():
    # DiarySection already renders the section <h2>; an agent's # or ## must not compete with it
    html = render("# Big\n\n## Medium")
    assert "<h3>Big</h3>" in html and "<h3>Medium</h3>" in html


def test_to_text_strips_markdown_to_plain_text():
    assert to_text("Stocks **rose** on [news](https://x.com).") == "Stocks rose on news."
