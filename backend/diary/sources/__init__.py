"""Where each gathering agent's material comes from. Scraped first, then handed to the model."""

from . import espn, google_news, spotify, yahoo
from .common import Item, Material

GATHERERS = {
    # every Google News feed, so the ranking weighs each story against all the day's news
    "major-events-editor": lambda date: google_news.gather(
        ("TOP", "WORLD", "NATION", "POLITICS", "BUSINESS", "TECHNOLOGY", "ENTERTAINMENT", "SPORTS", "SCIENCE", "HEALTH"),
        "breaking news", date),
    "political-analyst": lambda date: google_news.gather(("POLITICS", "WORLD"), "politics", date),
    "financial-analyst": lambda date: google_news.gather(("BUSINESS",), "business", date),
    "tech-analyst": lambda date: google_news.gather(("TECHNOLOGY",), "technology", date),
    "entertainment-curator": lambda date: google_news.gather(("ENTERTAINMENT",), "entertainment", date),
    "sports-analyst": espn.gather,
    "music-curator": spotify.gather,
    "stock-analyst": yahoo.gather,
}


def gather(agent, date: str) -> Material:
    return GATHERERS[agent.agent_id](date)


__all__ = ["GATHERERS", "Item", "Material", "gather"]
