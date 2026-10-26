from datetime import datetime, timezone
from pathlib import Path

from diary.sources import google_news
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


def test_window_is_the_24_hours_up_to_9am_new_york():
    start, end = window("2026-10-26")
    assert end == datetime(2026, 10, 26, 13, 0, tzinfo=timezone.utc)  # 9am EDT
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
    assert "after:2026-10-24" in urls[-1] and "before:2026-10-25" in urls[-1]
    assert material.items[0].publisher == "NPR"
