import json
from pathlib import Path

import pandas as pd
import pytest

from diary.sources import yahoo

FIXTURES = Path(__file__).parent / "fixtures"
IPOS = json.loads((FIXTURES / "yahoo_ipos.json").read_text())
MOVERS = json.loads((FIXTURES / "yahoo_movers.json").read_text())


def closes():
    return pd.DataFrame(
        {"^GSPC": [7700.0, 7600.0, 7623.68], "NVDA": [200.0, 210.0, 210.96]},
        index=pd.to_datetime(["2026-10-21", "2026-10-22", "2026-10-23"]),
    )


def test_changes_use_the_last_session_before_the_date():
    session, moves = yahoo.changes(closes(), "2026-10-26")
    assert session == "2026-10-23"
    close, pct = moves["^GSPC"]
    assert close == 7623.68 and pct == pytest.approx(0.3116, abs=1e-3)


def test_changes_ignore_sessions_on_or_after_the_date():
    session, moves = yahoo.changes(closes(), "2026-10-23")
    assert session == "2026-10-22" and moves["NVDA"][0] == 210.0


def test_ipos_drop_funds_rights_warrants_and_duplicates():
    symbols = [i.title.split("(")[1].split(")")[0] for i in yahoo.ipos(IPOS)]
    assert symbols.count("MSGR") == 1
    assert "LYCA" in symbols and "GUNN" in symbols
    for dropped in ("CAYN", "RADD", "WBMO", "PAXGR", "NANOW", "AHIC"):
        assert dropped not in symbols


def test_movers_only_from_the_last_session():
    items = yahoo.movers(MOVERS, "2026-10-23")
    assert any("RHI" in i.title and "+21.7%" in i.title for i in items)
    assert yahoo.movers(MOVERS, "2026-10-22") == []


def test_material_has_tables_and_citable_ipos():
    material = yahoo.build(closes(), IPOS, MOVERS, "2026-10-26")
    assert "Last session: 2026-10-23" in material.data
    assert "S&P 500 (^GSPC): 7,623.68 (+0.31%)" in material.data
    assert any(i.url == "https://finance.yahoo.com/quote/LYCA" for i in material.items)


def test_charts_carry_each_index_and_sector_session_but_not_stocks():
    material = yahoo.build(closes(), IPOS, MOVERS, "2026-10-23")  # the 23rd itself is excluded
    assert material.charts == [{"group": "Indices", "label": "S&P 500", "symbol": "^GSPC", "change": -1.3,
                                "closes": [7700.0, 7600.0]}]


def test_a_missing_ipo_section_is_added():
    material = yahoo.build(closes(), IPOS, MOVERS, "2026-10-26")
    md = material.ensure("### Major Indices\n\nStocks fell.")
    assert md.startswith("### IPOs\n")
    assert "Lycia Therapeutics" in md and md.endswith("Stocks fell.")


def test_an_existing_ipo_section_is_kept():
    material = yahoo.build(closes(), IPOS, MOVERS, "2026-10-26")
    md = "### IPO Watch\n\nQuiet week.\n\n### Major Indices\n\nUp."
    assert material.ensure(md) == md


def test_no_ipos_still_gets_a_section():
    material = yahoo.build(closes(), [], MOVERS, "2026-10-26")
    assert "No IPOs" in material.ensure("### Major Indices\n\nUp.")


def test_preferred_stock_offerings_are_not_ipos():
    record = {"Symbol": "SATS", "Company": "Strive, Inc. 15% Series A Perpetual SATS Preferred Stock",
              "Exchange": "Nasdaq", "Date": "2026-10-20T04:00:00.000Z"}
    assert yahoo.ipos([record]) == []
