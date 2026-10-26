"""Yahoo Finance via yfinance: last-session closes for indices, sectors, major stocks and macro
markets, the IPO calendar, and the day's biggest movers."""

import json
import re
import warnings
from datetime import date as Date, datetime, timedelta
from functools import partial

import pandas as pd
import yfinance as yf

from .common import NY, Item, Material

INDICES = {"^GSPC": "S&P 500", "^DJI": "Dow Jones Industrial Average", "^IXIC": "Nasdaq Composite",
           "^RUT": "Russell 2000", "^VIX": "VIX"}
SECTORS = {"XLK": "Technology", "XLF": "Financials", "XLE": "Energy", "XLV": "Health Care",
           "XLY": "Consumer Discretionary", "XLP": "Consumer Staples", "XLI": "Industrials",
           "XLB": "Materials", "XLU": "Utilities", "XLRE": "Real Estate", "XLC": "Communication Services"}
MAJOR = {"AAPL": "Apple", "MSFT": "Microsoft", "NVDA": "Nvidia", "AMZN": "Amazon", "GOOGL": "Alphabet",
         "META": "Meta", "TSLA": "Tesla", "AVGO": "Broadcom", "BRK-B": "Berkshire Hathaway", "JPM": "JPMorgan Chase"}
MACRO = {"^TNX": "10-Year Treasury Yield", "CL=F": "WTI Crude Oil", "GC=F": "Gold", "BTC-USD": "Bitcoin"}
GROUPS = (("Major indices", INDICES), ("Sectors (SPDR sector ETFs)", SECTORS),
          ("Major stocks", MAJOR), ("Rates, commodities and crypto", MACRO))
SCREENS = {"day_gainers": "Top gainer", "day_losers": "Top loser", "most_actives": "Most active"}
NOT_AN_IPO = re.compile(r"\b(ETFs?|Funds?|Trust|Rights|Warrants?|Units?|Preferred)\b", re.I)
IPO_HEADING = re.compile(r"^#{1,6}\s.*\bIPOs?\b", re.M | re.I)


def quote_url(symbol: str) -> str:
    return f"https://finance.yahoo.com/quote/{symbol}"


def changes(close: pd.DataFrame, date: str) -> tuple[str, dict[str, tuple[float, float]]]:
    """Close and % change for the last session before `date`, per symbol."""
    before = close[close.index < pd.Timestamp(date)]
    # crypto trades on weekends, so the session is the last day most symbols traded
    session = before.dropna(thresh=max(1, len(before.columns) // 2)).index[-1].date().isoformat()
    moves = {}
    for symbol in before.columns:
        col = before[symbol].dropna()
        if len(col) >= 2:
            moves[symbol] = (round(float(col.iloc[-1]), 2), float((col.iloc[-1] / col.iloc[-2] - 1) * 100))
    return session, moves


def ipos(records: list[dict]) -> list[Item]:
    out, seen = [], set()
    for r in sorted(records, key=lambda r: r.get("Date") or ""):
        symbol, name = r.get("Symbol"), r.get("Company") or ""
        if not symbol or not name or symbol in seen or NOT_AN_IPO.search(name):
            continue
        seen.add(symbol)
        lo, hi, price = r.get("Price From"), r.get("Price To"), r.get("Price")
        pricing = f"${lo:g}–${hi:g}" if lo and hi else f"${price:g}" if price else "price not set"
        out.append(Item(f"{name} ({symbol})", quote_url(symbol), "Yahoo Finance",
                        f"{r.get('Exchange') or 'exchange TBD'} · {(r.get('Date') or 'date TBD')[:10]} · {pricing}"))
    return out


def movers(screens: dict[str, list[dict]], session: str) -> list[Item]:
    out, seen = [], set()
    for key, quotes in screens.items():
        for q in quotes:
            t, symbol = q.get("regularMarketTime"), q.get("symbol")
            # screeners are live snapshots: only use them when they describe the session being reported
            if not t or symbol in seen or datetime.fromtimestamp(t, NY).date().isoformat() != session:
                continue
            seen.add(symbol)
            out.append(Item(f"{q.get('shortName') or symbol} ({symbol}) {q['regularMarketChangePercent']:+.1f}% "
                            f"at ${q['regularMarketPrice']:,.2f}", quote_url(symbol), "Yahoo Finance", SCREENS[key]))
    return out


def ensure_ipo_section(ipo_items: list[Item], md: str) -> str:
    """The stock section always opens with IPOs; if the model skipped them, add them from the data."""
    if IPO_HEADING.search(md):
        return md
    body = "\n".join(f"- **{i.title}** — {i.detail}" for i in ipo_items) or "No IPOs priced or scheduled around this date."
    return f"### IPOs\n\n{body}\n\n{md}"


def build(close: pd.DataFrame, ipo_records: list[dict], screens: dict[str, list[dict]], date: str) -> Material:
    session, moves = changes(close, date)
    lines = [f"Last session: {session}"]
    for heading, names in GROUPS:
        rows = [f"- {name} ({s}): {moves[s][0]:,.2f} ({moves[s][1]:+.2f}%)" for s, name in names.items() if s in moves]
        if rows:
            lines += ["", f"{heading}:", *rows]
    ipo_items = ipos(ipo_records)
    items = [Item("Yahoo Finance market data", "https://finance.yahoo.com/markets/", "Yahoo Finance",
                  f"closing levels and changes for {session}"), *ipo_items, *movers(screens, session)]
    return Material(items, data="\n".join(lines), ensure=partial(ensure_ipo_section, ipo_items))


def gather(date: str) -> Material:
    d = Date.fromisoformat(date)
    symbols = [s for _, names in GROUPS for s in names]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # yfinance's pandas deprecation noise
        close = yf.download(symbols, start=d - timedelta(days=10), end=d, progress=False, auto_adjust=False)["Close"]
        calendar = yf.Calendars(start=d - timedelta(days=7), end=d + timedelta(days=7)).get_ipo_info_calendar(limit=50)
        records = [] if calendar.empty else json.loads(calendar.reset_index().to_json(orient="records", date_format="iso"))
        screens = {key: yf.screen(key, count=5)["quotes"] for key in SCREENS}
    return build(close, records, screens, date)
