"""Spotify Web API: albums and singles released in the week before the date.

Uses /v1/search with the `tag:new` album filter (released in the past two weeks), because
/v1/browse/new-releases is deprecated (403 for this app). Client-credentials auth: no user login involved."""

import base64
import json
import os
from urllib.parse import quote
from datetime import UTC, date as Date, datetime, timedelta

from .common import Item, Material, get

TOKEN_URL = "https://accounts.spotify.com/api/token"
SEARCH_URL = "https://api.spotify.com/v1/search?q={query}&type=album&market=US&limit=10&offset={offset}"
# each query stops at 100 results, mostly the last two days' singles, so a mid-week entry missed the
# previous Friday's albums; words starting with each vowel reach further back.
# shortcut: still misses some releases; switch if Spotify adds a date filter to search
QUERIES = ("tag:new", *(f"tag:new {v}" for v in "aeiou"))
PAGES = 10  # 10 per page: the 100-result cap
MAX_ITEMS = 60


def token() -> str:
    pair = f"{os.environ['SPOTIFY_CLIENT_ID']}:{os.environ['SPOTIFY_CLIENT_SECRET']}"
    body = get(TOKEN_URL, data=b"grant_type=client_credentials", headers={
        "Authorization": "Basic " + base64.b64encode(pair.encode()).decode(),
        "Content-Type": "application/x-www-form-urlencoded",
    })
    return json.loads(body)["access_token"]


def search(token: str, query: str, offset: int) -> dict:
    return json.loads(get(SEARCH_URL.format(query=quote(query), offset=offset), headers={"Authorization": f"Bearer {token}"}))


def parse(page: dict) -> list[Item]:
    items = []
    for a in page["albums"]["items"]:
        released = a.get("release_date", "")
        n = a.get("total_tracks", 0)
        items.append(Item(
            title=f"{', '.join(x['name'] for x in a['artists'])} — {a['name']}",
            url=a["external_urls"]["spotify"],
            publisher="Spotify",
            detail=f"{a['album_type']} · {n} track{'s' if n != 1 else ''} · released {released}",
            # month/year-precision dates can't be placed in the week, so they're left undated and dropped
            published=datetime.fromisoformat(released).replace(tzinfo=UTC) if len(released) == 10 else None,
        ))
    return items


def gather(date: str) -> Material:
    if not (os.environ.get("SPOTIFY_CLIENT_ID") and os.environ.get("SPOTIFY_CLIENT_SECRET")):
        raise RuntimeError("SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set for the music section")
    t, items = token(), []
    for q in QUERIES:
        for p in range(PAGES):
            page = search(t, q, p * 10)
            items += parse(page)
            if not page["albums"].get("next"):
                break
    d = Date.fromisoformat(date)
    recent = [i for i in items if i.published and d - timedelta(days=7) <= i.published.date() <= d]
    # no popularity in search results; albums first (rarer, bigger news), then newest first
    recent.sort(key=lambda i: (i.detail.startswith("album"), i.published), reverse=True)
    return Material(list({i.url: i for i in reversed(recent)}.values())[::-1][:MAX_ITEMS])
