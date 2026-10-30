"""ESPN's public site API (no key): the previous day's final scores, with records and a one-line recap,
and each league's latest headlines."""

import json
from datetime import date as Date, datetime, timedelta

from .common import Item, Material, get, window

BASE = "https://site.api.espn.com/apis/site/v2/sports/{league}"
LEAGUES = {"football/nfl": "NFL", "basketball/nba": "NBA", "baseball/mlb": "MLB", "hockey/nhl": "NHL",
           "football/college-football": "College Football", "soccer/eng.1": "Premier League",
           "soccer/uefa.champions": "Champions League"}
MAX_ITEMS = 40


def record(team: dict) -> str:
    return f" ({team['records'][0]['summary']})" if team.get("records") else ""


def parse_scores(board: dict, league: str) -> list[Item]:
    items = []
    for e in board.get("events", []):
        c = e["competitions"][0]
        if not e["status"]["type"].get("completed"):
            continue
        teams = sorted(c["competitors"], key=lambda t: not t.get("winner"))  # winner first
        score = ", ".join(f"{t['team']['displayName']}{record(t)} {t.get('score', '')}" for t in teams)
        recap = (c.get("headlines") or [{}])[0].get("shortLinkText", "")
        # only playoff and title games have a note or a series, so detail stays empty for routine games
        marks = ((c.get("notes") or [{}])[0].get("headline", ""), (c.get("series") or {}).get("summary", ""))
        items.append(Item(f"{league}: {score}" + (f". {recap}" if recap else ""),
                          (e.get("links") or [{}])[0].get("href", "https://www.espn.com"), "ESPN",
                          " · ".join(m for m in marks if m)))
    return items


def parse_news(news: dict, league: str) -> list[Item]:
    return [Item(f"{league}: {a['headline']}", a["links"]["web"]["href"], "ESPN", a.get("description", "")[:300],
                 datetime.fromisoformat(a["published"].replace("Z", "+00:00")))
            for a in news.get("articles", []) if a.get("published")]


def gather(date: str) -> Material:
    start, end = window(date)
    day = (Date.fromisoformat(date) - timedelta(days=1)).strftime("%Y%m%d")  # last night's games
    scores, news = [], []
    for path, league in LEAGUES.items():
        scores += parse_scores(json.loads(get(f"{BASE.format(league=path)}/scoreboard?dates={day}")), league)
        # shortcut: /news only lists the latest stories, so a backfilled date gets scores only
        news += [i for i in parse_news(json.loads(get(f"{BASE.format(league=path)}/news?limit=10")), league)
                 if start < i.published <= end]
    # playoff and title games carry a note ("World Series - Game 5"); they lead
    scores.sort(key=lambda i: not i.detail)
    return Material((scores[:15] + news + scores[15:])[:MAX_ITEMS])
