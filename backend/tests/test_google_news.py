import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from diary.sources import Item, google_news
from diary.sources.common import window

FIXTURES = Path(__file__).parent / "fixtures"
TOPIC = (FIXTURES / "google_news_topic.xml").read_bytes()
SEARCH = (FIXTURES / "google_news_search.xml").read_bytes()


def test_parse_strips_the_publisher_suffix_and_keeps_the_link():
    first = google_news.parse(TOPIC)[0]
    assert first.title == "Opposition leader María Machado returns to Venezuela"
    assert first.publisher == "BBC"
    assert first.url.startswith("https://news.google.com/rss/articles/")
    assert first.published == datetime(2026, 10, 26, 3, 5, 22, tzinfo=timezone.utc)


def test_parse_keeps_other_outlets_coverage_as_detail():
    detail = google_news.parse(TOPIC)[0].detail
    assert "CNN" in detail and "The New York Times" in detail
    assert "BBC" not in detail  # the item's own outlet isn't repeated


def test_window_is_the_24_hours_up_to_5pm_new_york():
    start, end = window("2026-10-26")
    assert end == datetime(2026, 10, 26, 21, 0, tzinfo=timezone.utc)  # 5pm EDT
    assert (end - start).total_seconds() == 24 * 3600


def test_topic_feeds_are_used_when_they_cover_the_window(monkeypatch):
    urls = []
    monkeypatch.setattr(google_news, "fetch", lambda url: urls.append(url) or TOPIC)
    monkeypatch.setattr(google_news, "MIN_ITEMS", 1)
    material = google_news.gather(("POLITICS",), "politics", "2026-10-26")
    assert urls == [google_news.TOPIC_URL.format(topic="POLITICS")]
    start, end = window("2026-10-26")
    assert material.items and all(start < i.published <= end for i in material.items)


def test_two_topics_are_interleaved_and_deduplicated(monkeypatch):
    monkeypatch.setattr(google_news, "fetch", lambda url: TOPIC)
    monkeypatch.setattr(google_news, "MIN_ITEMS", 1)
    items = google_news.gather(("POLITICS", "WORLD"), "politics", "2026-10-26").items
    assert len(items) == len({i.title for i in items})


def test_past_dates_fall_back_to_the_dated_search_feed(monkeypatch):
    urls = []
    monkeypatch.setattr(google_news, "fetch", lambda url: urls.append(url) or (SEARCH if "search" in url else TOPIC))
    material = google_news.gather(("POLITICS",), "politics", "2026-10-25")
    assert "after:2026-10-25" in urls[-1] and "before:2026-10-26" in urls[-1]
    assert material.items[0].publisher == "NPR"


def test_top_stories_read_the_front_page_feed(monkeypatch):
    urls = []
    monkeypatch.setattr(google_news, "fetch", lambda url: urls.append(url) or TOPIC)
    monkeypatch.setattr(google_news, "MIN_ITEMS", 1)
    google_news.gather(("TOP",), "breaking news", "2026-10-26")
    assert urls == [google_news.TOP_URL]


def test_parse_counts_the_outlets_covering_a_story():
    assert [i.outlets for i in google_news.parse(TOPIC)] == [5] * 6  # the RSS lists at most 5
    assert all(i.outlets == 1 for i in google_news.parse(SEARCH))  # search results carry no cluster


def story(title, outlets=1):
    return Item(title, f"https://news.example/{title}", "Outlet", outlets=outlets)


def test_a_story_high_in_several_feeds_outranks_one_top_place():
    a, b, c, d = story("a"), story("b"), story("c"), story("d")
    assert [i.title for i in google_news.fuse([[a, b], [c, b, d]])][0] == "b"


def test_wider_coverage_breaks_a_tie_and_each_story_appears_once():
    a, b = story("a", outlets=1), story("b", outlets=5)
    fused = google_news.fuse([[a], [b], [b]])
    assert [i.title for i in fused] == ["b", "a"]
    assert [i.title for i in google_news.fuse([[a], [story("b", outlets=5)]])] == ["b", "a"]


def test_gather_ranks_a_story_in_more_feeds_first(monkeypatch):
    root = ET.fromstring(TOPIC)
    channel = root.find("channel")
    fifth = channel.findall("item")[4]
    for it in channel.findall("item"):
        if it is not fifth:
            channel.remove(it)
    only_fifth = ET.tostring(root)  # a second feed that carries only the top feed's fifth story
    monkeypatch.setattr(google_news, "fetch", lambda url: TOPIC if url == google_news.TOP_URL else only_fifth)
    monkeypatch.setattr(google_news, "MIN_ITEMS", 1)
    items = google_news.gather(("TOP", "WORLD"), "breaking news", "2026-10-26").items
    assert items[0].title == google_news.parse(TOPIC)[4].title
    assert len(items) == len({i.title for i in items})
