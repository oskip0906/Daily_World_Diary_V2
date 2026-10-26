"""CLI: python -m diary.generate [--date YYYY-MM-DD] [--force] [--dry-run]"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from . import pipeline, store
from .agent import AgentResult

log = logging.getLogger("diary")


async def stub(agent, date, context=None) -> AgentResult:
    sources = [{"title": "Example source", "url": "https://example.com"}] if agent.searches else []
    return AgentResult(f"### {agent.section_title}\n\nStub text for {date}. **No model was called.**", sources)


def date_arg(value: str) -> str:
    if not store.DATE.match(value):
        raise argparse.ArgumentTypeError("use YYYY-MM-DD")
    return value


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="diary.generate")
    parser.add_argument("--date", type=date_arg,
                        default=datetime.now(ZoneInfo("America/New_York")).date().isoformat())
    parser.add_argument("--force", action="store_true", help="overwrite an existing entry")
    parser.add_argument("--dry-run", action="store_true", help="stub agents, validate, write nothing")
    args = parser.parse_args(argv)

    if args.dry_run:
        entry = asyncio.run(pipeline.generate(args.date, run=stub))
        pipeline.check_contract(entry)
        print(json.dumps({"sections": [s["id"] for s in entry["sections"]], "metadata": entry["metadata"]}, indent=2))
        return 0

    # check before generating: a re-run must not burn API spend on a date that already has an entry
    if store.read(args.date) is not None and not args.force:
        log.error("%s already exists; pass --force to regenerate", args.date)
        return 1

    entry = asyncio.run(pipeline.generate(args.date))
    pipeline.check_contract(entry)
    if not entry["sections"]:
        log.error("%s: every agent failed, nothing written", args.date)
        return 1
    store.write(entry, force=args.force)
    store.write_prompts(pipeline.prompts_payload())
    log.info("%s: wrote %d sections, usage %s", args.date, len(entry["sections"]), entry["usage"])
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    sys.exit(main())
