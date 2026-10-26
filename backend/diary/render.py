"""Markdown -> sanitized HTML. Section content is model output derived from web pages and the
frontend injects it with dangerouslySetInnerHTML, so everything goes through an allowlist."""

import html
import re

import markdown
import nh3

TAGS = {"h3", "h4", "p", "ul", "ol", "li", "strong", "em", "a", "blockquote", "code", "pre", "hr", "br"}
ATTRS = {"a": {"href", "title"}}
SCHEMES = {"http", "https"}


def render(md: str) -> str:
    out = markdown.markdown(md)
    # DiarySection renders the section's own <h2>; demote anything at or above it
    out = re.sub(r"<(/?)h[12]>", r"<\1h3>", out)
    return nh3.clean(out, tags=TAGS, attributes=ATTRS, url_schemes=SCHEMES)


def to_text(md: str) -> str:
    text = nh3.clean(markdown.markdown(md), tags=set())
    return " ".join(html.unescape(text).split())
