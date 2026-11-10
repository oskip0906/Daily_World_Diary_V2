"""Google News section feeds (RSS): ranked headlines per topic, with other outlets' coverage of each story,
merged into one ranking by importance and popularity."""

import html
import re
import xml.etree.ElementTree as ET
from datetime import date as Date, timedelta
from email.utils import parsedate_to_datetime
from itertools import chain
from urllib.parse import quote_plus

from .common import Item, Material, get as fetch, window

TOPIC_URL = "https://news.google.com/rss/headlines/section/topic/{topic}?hl=en-US&gl=US&ceid=US:en"
TOP_URL = "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"  # the front page: Top stories, ranked
SEARCH_URL = "https://news.google.com/rss/search?q={query}+after:{start}+before:{end}&hl=en-US&gl=US&ceid=US:en"
MIN_ITEMS = 10
MAX_ITEMS = 30
K = 60  # reciprocal rank fusion's usual constant: being in several rankings outweighs one top place
RELATED = re.compile(r"<a [^>]*>(.*?)</a>(?:&nbsp;|\s)*<font[^>]*>(.*?)</font>", re.S)


def parse(xml: bytes) -> list[Item]:
    items = []
    for it in ET.fromstring(xml).iterfind("./channel/item"):
        publisher = it.findtext("source") or ""
        title = it.findtext("title") or ""
        title = title.removesuffix(f" - {publisher}") if publisher else title
        related = [(html.unescape(t), html.unescape(p)) for t, p in RELATED.findall(it.findtext("description") or "")]
        also = "; ".join(f"{p}: {t}" for t, p in related if p != publisher)[:600]
        items.append(Item(title, it.findtext("link") or "", publisher, f"Also: {also}" if also else "",
                          parsedate_to_datetime(it.findtext("pubDate")), len({publisher, *(p for _, p in related)})))
    return items


def fuse(rankings: list[list[Item]]) -> list[Item]:
    """Every story once, most important first, by reciprocal rank fusion: a story scores 1 / (K + place) in
    each ranking it is in. The rankings are Google's own feeds (importance) plus one by how many outlets
    cover the story (popularity), so a story high in several feeds and widely covered leads. The RSS lists at
    most 5 outlets per story, so that ranking mostly sinks single-source stories; carrying feeds weigh more."""
    stories = {}
    for i in chain.from_iterable(rankings):
        stories.setdefault(i.title, i)  # first occurrence wins
    score = dict.fromkeys(stories, 0.0)
    for ranking in [*rankings, sorted(stories.values(), key=lambda i: -i.outlets)]:
        for place, i in enumerate(ranking):
            score[i.title] += 1 / (K + place)
    return sorted(stories.values(), key=lambda i: -score[i.title])


def gather(topics: tuple[str, ...], query: str, date: str) -> Material:
    start, end = window(date)
    feeds = [[i for i in parse(fetch(TOP_URL if t == "TOP" else TOPIC_URL.format(topic=t))) if start < i.published <= end]
             for t in topics]
    if sum(map(len, feeds)) < MIN_ITEMS:
        # topic feeds only hold the last ~2 days; a backfilled date needs the dated search feed
        d = Date.fromisoformat(date)
        feeds = [parse(fetch(SEARCH_URL.format(query=quote_plus(query), start=d, end=d + timedelta(days=1))))]
    return Material(fuse(feeds)[:MAX_ITEMS])
