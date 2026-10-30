import pytest

from diary.sources import spotify


def album(name, artists, released, kind="album", tracks=10):
    """Shape of a SimplifiedAlbumObject in /v1/search?type=album, per Spotify's API reference."""
    return {"name": name, "album_type": kind, "total_tracks": tracks, "release_date": released,
            "release_date_precision": "day", "external_urls": {"spotify": f"https://open.spotify.com/album/{name}"},
            "artists": [{"name": a} for a in artists]}


def page(*albums):
    return {"albums": {"items": list(albums), "next": None}}


def test_parse_names_artists_and_release():
    item = spotify.parse(page(album("Midnights II", ["Taylor Swift", "Lana Del Rey"], "2026-10-23")))[0]
    assert item.title == "Taylor Swift, Lana Del Rey — Midnights II"
    assert item.url == "https://open.spotify.com/album/Midnights II"
    assert item.publisher == "Spotify"
    assert item.detail == "album · 10 tracks · released 2026-10-23"


def test_gather_keeps_the_week_before_the_date_newest_first(monkeypatch):
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "secret")
    monkeypatch.setattr(spotify, "token", lambda: "t")
    monkeypatch.setattr(spotify, "search", lambda token, query, offset: page(
        album("Old", ["A"], "2026-10-01"),
        album("Fresh", ["B"], "2026-10-24", kind="single", tracks=1),
        album("Newer", ["C"], "2026-10-25"),
        album("Future", ["D"], "2026-10-30"),
    ) if offset == 0 else page())
    titles = [i.title for i in spotify.gather("2026-10-26").items]
    assert titles == ["C — Newer", "B — Fresh"]


def test_missing_credentials_fail_loudly(monkeypatch):
    monkeypatch.delenv("SPOTIFY_CLIENT_ID", raising=False)
    monkeypatch.delenv("SPOTIFY_CLIENT_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="SPOTIFY_CLIENT_ID"):
        spotify.gather("2026-10-26")


def test_albums_come_before_newer_singles(monkeypatch):
    # search results carry no popularity, and singles vastly outnumber albums; albums are the rarer, bigger news
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "secret")
    monkeypatch.setattr(spotify, "token", lambda: "t")
    monkeypatch.setattr(spotify, "search", lambda token, query, offset: page(
        album("Single", ["A"], "2026-10-26", kind="single", tracks=1),
        album("LP", ["B"], "2026-10-21"),
    ) if offset == 0 else page())
    assert [i.title for i in spotify.gather("2026-10-26").items] == ["B — LP", "A — Single"]


def test_vowel_queries_reach_albums_the_plain_query_misses(monkeypatch):
    # tag:new stops at 100 results, which mid-week are all recent singles
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "secret")
    monkeypatch.setattr(spotify, "token", lambda: "t")
    found = {"tag:new": album("Single", ["A"], "2026-10-26", kind="single", tracks=1),
             "tag:new e": album("Friday LP", ["B"], "2026-10-23")}
    monkeypatch.setattr(spotify, "search", lambda token, query, offset: page(
        *[found[query]] if query in found and offset == 0 else []))
    assert [i.title for i in spotify.gather("2026-10-26").items] == ["B — Friday LP", "A — Single"]
