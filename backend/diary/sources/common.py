"""What every source hands an agent: citable items plus optional preformatted figures."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date as Date, datetime, time, timedelta
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
USER_AGENT = "Mozilla/5.0 (compatible; DailyWorldDiary/1.0)"


@dataclass(frozen=True)
class Item:
    title: str
    url: str
    publisher: str
    detail: str = ""
    published: datetime | None = None


@dataclass
class Material:
    items: list[Item]
    data: str = ""  # figures the model reads but can't cite by number (e.g. market tables)
    ensure: Callable[[str], str] = field(default=lambda md: md)  # guarantee applied to the model's output


def window(date: str) -> tuple[datetime, datetime]:
    """The 24 hours a date's entry covers: up to 9am New York that morning, when the Action runs."""
    end = datetime.combine(Date.fromisoformat(date), time(9), tzinfo=NY).astimezone(UTC)
    return end - timedelta(hours=24), end


def get(url: str, headers: dict | None = None, data: bytes | None = None) -> bytes:
    request = Request(url, data=data, headers={"User-Agent": USER_AGENT, **(headers or {})})
    with urlopen(request, timeout=30) as response:
        return response.read()
