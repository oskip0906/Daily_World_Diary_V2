"""Google News section feeds (RSS): ranked headlines per topic, with other outlets' coverage of each story."""

import html
import re
import xml.etree.ElementTree as ET
from datetime import date as Date, timedelta
from email.utils import parsedate_to_datetime
from itertools import chain, zip_longest
from urllib.parse import quote_plus

from .common import Item, Material, get as fetch, window

TOPIC_URL = "https://news.google.com/rss/headlines/section/topic/{topic}?hl=en-US&gl=US&ceid=US:en"
SEARCH_URL = "https://news.google.com/rss/search?q={query}+after:{start}+before:{end}&hl=en-US&gl=US&ceid=US:en"
MIN_ITEMS = 10
MAX_ITEMS = 30
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
                          parsedate_to_datetime(it.findtext("pubDate"))))
    return items


def gather(topics: tuple[str, ...], query: str, date: str) -> Material:
    start, end = window(date)
    feeds = [parse(fetch(TOPIC_URL.format(topic=t))) for t in topics]
    ranked = [i for i in chain.from_iterable(zip_longest(*feeds)) if i]  # interleave: keep each feed's ranking
    items = [i for i in ranked if start < i.published <= end]
    if len(items) < MIN_ITEMS:
        # topic feeds only hold the last ~2 days; a backfilled date needs the dated search feed
        d = Date.fromisoformat(date)
        items = parse(fetch(SEARCH_URL.format(query=quote_plus(query), start=d - timedelta(days=1), end=d)))
    unique = list({i.title: i for i in reversed(items)}.values())[::-1]  # first occurrence wins
    return Material(unique[:MAX_ITEMS])
