"""Story threads: one model call links today's stories to the same developing stories earlier in the
week, so the page can tag a card "Day 4 · Serbia's student protests" and a thread page can follow
the story over time.

Entries are write-once, so an earlier story is never edited. Instead today's entry records, for each
of its threaded stories, every earlier story of that thread (`follows`). The latest entry of a thread
therefore lists all of it, which is what the thread page reads."""

import html
import json
import logging
import re

import nh3
import openai

from . import store
from .agent import client, model

log = logging.getLogger(__name__)

LOOKBACK_DAYS = 7
MAX_RETRIES = 2  # retries after the first attempt
MAX_TOKENS = 4000
SNIPPET = 280  # characters of each story the model sees
ACCOUNT_STATUSES = {401, 402, 403}
# Only news sections: the 2026-10-26 trial threaded the daily market wrap, the week's same Spotify
# releases and the Outlook's recaps, which recur every day without being developing stories
THREAD_SECTIONS = {"political-news", "financial-news", "entertainment-news"}
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+){0,7}$")
FENCE = re.compile(r"^```[a-z]*\s*\n(?P<body>.*?)\n```$", re.S)
CITATION_LINK = re.compile(r"\s*<a [^>]*>[^<]*</a>")

PROMPT = """You keep the running threads of Daily World Diary, a daily news digest. Each morning you read today's stories and the past week's, and you link today's stories to the earlier stories they continue, so a reader can follow a developing story day by day. The page then tags the story "Day 4 · <thread title>" and links to a page that shows the whole thread.

A thread is one developing story: an election campaign, a war or a ceasefire, a trial, a strike, a merger, a protest movement, a policy fight, a company's crisis. Link today's story to earlier ones only when it is the same story moving forward, meaning the same event or process. Sharing a person, a country, a company or a topic is not enough: "Trump" is not a thread, "the Russian diesel sanctions deal" is. A routine market wrap is not a thread just because markets moved again, but a specific continuing market story (an AI spending sell-off, say) can be.

Rules:
- Each of today's stories belongs to at most one thread, and most belong to none. Precision matters far more than coverage: a wrong link misleads readers, a missing one costs little.
- Past stories already in a thread are marked [thread <id>: <title>]. To continue that thread, use its id, and keep its title unless the story has clearly changed.
- A new thread needs at least one earlier story it continues, listed in "follows".
- "follows" holds refs from the past week's list, copied exactly. Include every earlier story of this thread you can see there, not only the latest.
- Ids are short lowercase slugs: letters, digits and hyphens, e.g. "serbia-student-protests".
- Titles are 2-6 words naming the specific story so it reads well after "Day 4 ·", e.g. "Serbia's student protests" or "Netflix's leadership shakeup". No dates, no "Day".
- If the best title you can give is a category ("Entertainment business moves", "Local news", "Market moves", "Midterm campaigns" in general), it is not a thread: leave the story out.

Reply with JSON only, no prose and no Markdown fences:
{"threads": [{"story": "<today's ref>", "id": "<slug>", "title": "<title>", "follows": ["<past ref>", ...]}]}
If nothing continues, reply {"threads": []}."""


def split(content: str) -> list[tuple[str | None, str]]:
    """Section HTML -> (title HTML, body HTML) per story. Mirrors splitStories in
    website/src/components/StoryCard.tsx, so story n here is card n on the page."""
    out = []
    for chunk in (c.strip() for c in re.split(r"(?=<h3>)", content)):
        if chunk:
            m = re.match(r"^<h3>(.*?)</h3>\s*(.*)$", chunk, re.S)
            out.append((m[1], m[2]) if m else (None, chunk))
    return out


def _text(fragment: str) -> str:
    return " ".join(html.unescape(nh3.clean(CITATION_LINK.sub("", fragment), tags=set())).split())


def stories(entry: dict) -> dict[str, str]:
    """"<section id>/<n>" (n from 1) -> "Title: start of the text" for every story the page shows."""
    out = {}
    for s in entry["sections"]:
        if s["id"] not in THREAD_SECTIONS:
            continue
        for n, (title, body) in enumerate(split(s["content"]), 1):
            text = _text(body)
            out[f"{s['id']}/{n}"] = f"{_text(title) if title else s['title']}: " \
                                    f"{text[:SNIPPET] + ('…' if len(text) > SNIPPET else '')}"
    return out


def history(date: str) -> tuple[dict[str, str], dict[str, dict]]:
    """-> (past-week story refs "date/section/n" -> line, threads so far: id -> {"title", "members"})."""
    dates = [d for d in store.list_dates() if d < date]
    threads: dict[str, dict] = {}
    for d in dates:  # oldest first, so a later entry's fuller member list wins
        for t in (store.read(d) or {}).get("threads", []):
            threads[t["id"]] = {"title": t["title"], "members": [*t["follows"], f"{d}/{t['story']}"]}
    member_of = {ref: tid for tid, t in threads.items() for ref in t["members"]}
    past = {}
    for d in dates[-LOOKBACK_DAYS:]:
        for ref, line in stories(store.read(d) or {"sections": []}).items():
            ref = f"{d}/{ref}"
            tid = member_of.get(ref)
            past[ref] = f"[thread {tid}: {threads[tid]['title']}] {line}" if tid else line
    return past, threads


def context(date: str, today: dict[str, str], past: dict[str, str]) -> str:
    return (f"Today is {date}. Today's stories:\n" + "\n".join(f"- {r} {line}" for r, line in today.items())
            + "\n\nThe past week's stories, oldest first:\n"
            + ("\n".join(f"- {r} {line}" for r, line in past.items()) or "- none"))


def validate(raw: str, today: dict[str, str], past: dict[str, str], threads: dict[str, dict]) -> list[dict]:
    """The model's reply -> the entry's thread records. Raises ValueError saying what to fix when the
    reply is malformed; picks that are well-formed but inconsistent are repaired or dropped instead,
    because rejecting a whole reply over one of them lost two days' threads in testing."""
    body = raw.strip()
    if m := FENCE.match(body):
        body = m["body"].strip()
    try:
        picks = json.loads(body)["threads"]
    except (ValueError, KeyError, TypeError):
        raise ValueError('the reply must be JSON of the form {"threads": [...]}') from None
    if not isinstance(picks, list):
        raise ValueError('"threads" must be a list')
    member_of = {ref: tid for tid, t in threads.items() for ref in t["members"]}
    out, seen = [], set()
    for p in picks:
        if not isinstance(p, dict):
            raise ValueError("each thread must be an object with story, id, title and follows")
        story, tid, title, follows = p.get("story"), p.get("id"), p.get("title"), p.get("follows") or []
        if story not in today:
            raise ValueError(f"story {story!r} is not one of today's refs")
        if story in seen:
            log.info("threads: %s picked twice; keeping its first thread", story)
            continue
        if not isinstance(tid, str) or not SLUG.match(tid):
            raise ValueError(f"id {tid!r} must be a lowercase slug like serbia-student-protests")
        if not isinstance(title, str) or not 3 <= len(title.strip()) <= 60 or "<" in title:
            raise ValueError(f"title {title!r} for {story} must be 3-60 characters")
        if not isinstance(follows, list) or any(r not in past for r in follows):
            bad = [r for r in follows if r not in past] if isinstance(follows, list) else follows
            raise ValueError(f"follows for {story} has refs that aren't in the past week's list: {bad}")
        other = sorted({member_of[r] for r in follows if r in member_of} - {tid})
        if other and tid not in threads:
            # it follows stories of an existing thread under a new id: it continues that thread
            tid, title = other[0], threads[other[0]]["title"]
        if tid not in threads and not follows:
            log.info("threads: new thread %s follows nothing; dropped", tid)
            continue
        seen.add(story)
        members = sorted(set(threads.get(tid, {}).get("members", [])) | set(follows))
        out.append({"id": tid, "title": title.strip(), "story": story,
                    "day": len({r.split("/")[0] for r in members}) + 1, "follows": members})
    return out


async def run_threads(entry: dict) -> tuple[list[dict], dict]:
    """-> (the entry's thread records, usage summed over every attempt). Never raises on a bad reply
    or a provider error: a day without threads is still a complete entry."""
    date = entry["metadata"]["date"]
    today = stories(entry)
    past, threads = history(date)
    if not today or not past:
        return [], {}
    messages = [{"role": "system", "content": PROMPT}, {"role": "user", "content": context(date, today, past)}]
    usage: dict = {}
    for attempt in range(1 + MAX_RETRIES):
        try:
            resp = await client().chat.completions.create(
                model=model(), messages=messages, max_tokens=MAX_TOKENS,
                extra_headers={"X-Title": "Daily World Diary"},
                extra_body={"reasoning": {"enabled": False}},  # see agent.run_agent
            )
        except openai.APIStatusError as e:
            if e.status_code in ACCOUNT_STATUSES:
                log.warning("threads: OpenRouter rejected the key (%s); no threads", e.status_code)
                return [], usage
            log.warning("threads attempt %d failed: %s", attempt + 1, e)
            continue
        except openai.APIError as e:
            log.warning("threads attempt %d failed: %s", attempt + 1, e)
            continue
        for k, v in (resp.usage.model_dump() if resp.usage else {}).items():
            if isinstance(v, (int, float)):
                usage[k] = usage.get(k, 0) + v
        reply = resp.choices[0].message.content or ""
        try:
            linked = validate(reply, today, past, threads)
        except ValueError as e:
            log.warning("threads attempt %d rejected: %s", attempt + 1, e)
            messages += [{"role": "assistant", "content": reply},
                         {"role": "user", "content": f"That was rejected: {e}. Reply with the corrected JSON only."}]
            continue
        log.info("threads: %d linked after %d attempt(s)", len(linked), attempt + 1)
        return linked, usage
    log.warning("threads: no valid reply after %d attempts; no threads", 1 + MAX_RETRIES)
    return [], usage
