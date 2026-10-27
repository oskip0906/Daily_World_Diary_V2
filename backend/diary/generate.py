"""CLI: python -m diary.generate [--date YYYY-MM-DD] [--force] [--dry-run] | --redesign [YYYY-MM-DD ...]"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from . import pipeline, store
from .agent import AgentResult
from .sources import Item, Material

log = logging.getLogger("diary")


async def stub(agent, date, context=None, material=None) -> AgentResult:
    return AgentResult(f"### {agent.section_title}\n\nStub text for {date}. **No model was called.**")


async def stub_design(date, title, summary, sections):
    return None, {}


async def stub_threads(entry):
    return [], {}


def stub_scrape(agent, date) -> Material:
    return Material([Item("Example source", "https://example.com", "Example")])


def date_arg(value: str) -> str:
    if not store.DATE.match(value):
        raise argparse.ArgumentTypeError("use YYYY-MM-DD")
    return value


async def redesign(dates: list[str]) -> int:
    """Only the design step again, oldest first so each day sees the one before. The text is kept,
    and a day whose design fails keeps the theme it had. One event loop for every day: the cached
    OpenRouter client is bound to the loop it first ran in."""
    failed = 0
    for date in sorted(dates):
        entry = store.read(date)
        theme, usage = await pipeline.redesign(entry) if entry else (None, {})
        if not theme:
            log.error("%s: %s; left as it was", date, "no valid design" if entry else "no entry")
            failed += 1
            continue
        entry["theme"] = theme
        entry["usage"] = {k: (entry["usage"].get(k) or 0) + (usage.get(k) or 0) for k in pipeline.USAGE_KEYS}
        pipeline.check_contract(entry)
        store.write(entry, force=True)
        log.info("%s: redesigned as %r, mood %s", date, theme["name"], theme["mood"])
    return 1 if failed else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="diary.generate")
    parser.add_argument("--date", type=date_arg,
                        default=datetime.now(ZoneInfo("America/New_York")).date().isoformat())
    parser.add_argument("--force", action="store_true", help="overwrite an existing entry")
    parser.add_argument("--dry-run", action="store_true", help="stub scrapers and agents, validate, write nothing")
    parser.add_argument("--redesign", nargs="*", type=date_arg, metavar="DATE",
                        help="re-run only the design step on existing entries (default: every entry)")
    args = parser.parse_args(argv)

    if args.redesign is not None:
        return asyncio.run(redesign(args.redesign or store.list_dates()))

    if args.dry_run:
        entry = asyncio.run(pipeline.generate(args.date, run=stub, scrape=stub_scrape, design=stub_design, link=stub_threads))
        pipeline.check_contract(entry)
        print(json.dumps({"sections": [s["id"] for s in entry["sections"]], "metadata": entry["metadata"]}, indent=2))
        return 0

    # check before generating: a re-run must not burn API spend on a date that already has an entry
    if store.read(args.date) is not None and not args.force:
        log.error("%s already exists; pass --force to regenerate", args.date)
        return 1

    try:
        entry = asyncio.run(pipeline.generate(args.date))
    except pipeline.AccountError as e:
        log.error("%s: %s. Nothing written; re-run once the key works.", args.date, e)
        return 1
    pipeline.check_contract(entry)
    if not entry["sections"]:
        log.error("%s: every agent failed, nothing written", args.date)
        return 1
    store.write(entry, force=args.force)
    log.info("%s: wrote %d sections, usage %s", args.date, len(entry["sections"]), entry["usage"])
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    sys.exit(main())
