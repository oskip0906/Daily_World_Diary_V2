"""The day's look: one last model call reads the finished entry and designs its page.

It picks a header style and, for every section, one of ten card components and one of six layouts,
then writes the CSS on top. The CSS is injected into the page as-is, so it is treated as untrusted
input: parsed, scoped to .diary-page, stripped of anything that loads a resource, and checked for
readable contrast. To keep days from looking alike, the model sees the last few days' designs and
the picks must vary. A rejected design goes back to the model with the reason, up to MAX_RETRIES
times."""

import logging
import re
import textwrap
from datetime import date as Date
from functools import cache
from pathlib import Path

import openai
import tinycss2

from . import store
from .agent import client, model

log = logging.getLogger(__name__)

MAX_RETRIES = 5  # retries after the first attempt
MAX_TOKENS = 14000
MAX_CSS = 24000
HISTORY_DAYS = 4
ACCOUNT_STATUSES = {401, 402, 403}  # retrying a rejected key only burns time

# The components the frontend implements (website/src/components/StoryCard.tsx, globals.css)
HEROES = {
    "classic": "left-aligned headline with the summary below it",
    "centered": "headline, summary and theme note centred in a narrower column",
    "split": "on wide screens the headline sits on the left and the summary on the right",
    "poster": "a full-bleed block of --accent with a very large headline; all header text uses --accent-ink",
}
CARDS = {
    "plain": "no box at all: the story flows as editorial text",
    "outline": "a box drawn with a --rule border",
    "elevated": "a raised panel with a shadow",
    "banner": "the story headline sits in an --accent band across the top of the box",
    "split": "the headline in a narrow left column, the text on the right (stacks when the card is narrow)",
    "numbered": "a large index number (01, 02...) beside the story",
    "lede": "the story's first paragraph is pulled out large, like a magazine standfirst",
    "stat": "the first figure in the story (a percentage, dollar amount or number) is shown huge above the headline",
    "timeline": "stories hang off a vertical rail with a dot at each headline",
    "tile": "a solid --paper-alt block",
}
LAYOUTS = {
    "stack": "one column at reading width",
    "grid-2": "two columns",
    "grid-3": "three columns on wide screens, two on medium",
    "feature": "the first story spans the full width, the rest sit in two columns below it",
    "masonry": "two columns of uneven height, like a newspaper page",
    "rail": "one row of cards that scrolls sideways",
}
MIN_CARDS, MIN_LAYOUTS = 3, 2  # distinct choices per page, so a page is never one card repeated

COLOR_TOKENS = ("--paper", "--paper-alt", "--ink", "--ink-soft", "--muted", "--accent", "--accent-ink", "--rule")
FONT_TOKENS = ("--font-display", "--font-body", "--font-ui")
# (foreground, background, minimum WCAG contrast ratio)
# the header (kicker, crumbs, theme note) and tiles sit on --paper-alt, the article on --paper
CONTRAST = (("--ink", "--paper", 7), ("--ink", "--paper-alt", 7),
            ("--ink-soft", "--paper", 4.5), ("--ink-soft", "--paper-alt", 4.5),
            ("--muted", "--paper", 4.5), ("--muted", "--paper-alt", 4.5),
            ("--accent", "--paper", 4.5), ("--accent", "--paper-alt", 4.5),
            ("--accent-ink", "--accent", 4.5))
AT_RULES = {"media", "supports", "container", "keyframes"}
BANNED_FUNCTIONS = {"url", "image", "image-set", "-webkit-image-set", "cross-fade", "element", "expression",
                    "src", "paint", "env", "attr"}
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
ORNAMENT = re.compile(r"::?(before|after|marker)\b")
UNIVERSAL = re.compile(r"\*(::?[\w-]+)*$")  # a selector whose last part is *
SCOPE = re.compile(r"^\.diary-page(?![\w-])")
FONT_VAR = re.compile(r"var\((--ff-[\w-]+)\)")
HEADER = re.compile(r"^/\*\s*theme:\s*(?P<name>[^|*]{2,60}?)\s*\|\s*(?P<note>[^*]{10,240}?)\s*\*/\s*"
                    r"/\*\s*layout:\s*(?P<layout>[^*]+?)\s*\*/")
FENCE = re.compile(r"^```[a-z]*\s*\n(?P<css>.*?)\n```$", re.S)
GLOBALS_CSS = Path(__file__).resolve().parents[2] / "website" / "src" / "app" / "globals.css"

FONTS = {
    "--ff-fraunces": "Fraunces, a soft, high-contrast display serif (variable weight 300-900)",
    "--ff-playfair": "Playfair Display, a classic, dramatic didone serif",
    "--ff-dm-serif": "DM Serif Display, a punchy, tightly spaced headline serif (weight 400 only)",
    "--ff-instrument": "Instrument Serif, an elegant condensed serif for large, quiet headlines (weight 400 only)",
    "--ff-newsreader": "Newsreader, a serif designed for long reading at text sizes",
    "--ff-inter": "Inter, a neutral, highly legible sans-serif",
    "--ff-space-grotesk": "Space Grotesk, a geometric sans with a technical, contemporary edge",
    "--ff-syne": "Syne, a wide, eccentric art-school sans for headlines (variable weight 400-800)",
    "--ff-unbounded": "Unbounded, a round, wide, loud display sans (variable weight 200-900)",
    "--ff-archivo-black": "Archivo Black, a heavy grotesque for blunt, poster-like headlines (weight 400 only)",
    "--ff-bebas": "Bebas Neue, an all-caps condensed display face (headlines only, never body text)",
    "--ff-plex-mono": "IBM Plex Mono, a monospace (weights 400 and 600)",
}

# Mirrors website/src/app/diary/[date]/page.tsx, StoryCard.tsx and TableOfContents.tsx: keep them in step.
PAGE = """<div class="diary-page" id="top" data-date="2026-10-26" data-hero="split">
  <style>/* your stylesheet goes here */</style>
  <header class="diary-hero">
    <div class="diary-hero-inner">
      <nav class="diary-crumbs"><a href="/calendar">All entries</a></nav>
      <p class="diary-kicker">Monday edition</p>
      <h1 class="diary-title">World Digest — October 26, 2026</h1>
      <p class="diary-summary">The 2-3 sentence summary of the day.</p>
      <p class="diary-theme-note"><span class="diary-theme-name">Your theme name</span> Your one-sentence note.</p>
    </div>
  </header>
  <div class="diary-body">
    <aside class="diary-toc">
      <nav class="diary-toc-nav">
        <p class="diary-toc-label">In this edition</p>
        <ol class="diary-toc-list">
          <li><a class="diary-toc-link is-active" href="#political-news"><span class="diary-toc-number">01</span> Political News</a></li>
          <!-- one per section; .is-active marks the section being read -->
        </ol>
        <a class="diary-toc-top" href="#top">↑ Back to top</a>
      </nav>
    </aside>
    <article class="diary-article">
      <section class="diary-section" id="political-news" data-section="political-news" data-card="banner" data-layout="grid-2">
        <header class="diary-section-head">
          <span class="diary-section-number">01</span>
          <h2 class="diary-section-title">Political News</h2>
        </header>
        <ul class="diary-markets">  <!-- stock-analysis only: one small chart per index and sector -->
          <li class="diary-spark is-up">  <!-- is-up or is-down -->
            <span class="diary-spark-label">S&P 500</span>
            <span class="diary-spark-value">7,612.57</span>
            <span class="diary-spark-change">▲ 0.28%</span>
            <svg class="diary-spark-line"><polyline stroke="currentColor" /></svg>  <!-- the last week's closes -->
          </li>
        </ul>
        <div class="diary-stories diary-stories--grid-2">
          <!-- one card per story; a story is one ### heading of the section and the text under it -->
          <article class="diary-card diary-card--banner">  <!-- a size container: @container queries see the card's width -->
            <div class="diary-card-inner">
              <span class="diary-card-index">01</span>              <!-- numbered cards only -->
              <p class="diary-card-figure">+3.4%</p>                 <!-- stat cards only, when the story has a figure -->
              <h3 class="diary-card-title">Europe</h3>              <!-- absent for text before a section's first heading -->
              <a class="diary-card-thread" href="/threads/serbia-student-protests">Day 4 · Serbia's student protests</a>  <!-- stories that continue an earlier one -->
              <p class="diary-card-lede">The first paragraph.</p>   <!-- lede cards only -->
              <div class="diary-card-body diary-prose">
                <!-- the story text: only h4, p, ul, ol, li, strong, em, blockquote, code, pre, hr, br and a.
                     Each a is a citation: a publisher name linking to the article, right after the sentence it supports.
                     In music-releases each Spotify citation is instead a player:
                     <iframe class="diary-embed" height="152"> (Spotify's own widget: style its box, not its inside) -->
              </div>
            </div>
          </article>
        </div>
      </section>
      <!-- more sections -->
    </article>
  </div>
  <footer class="diary-footer">
    <a class="diary-footer-prev" href="/diary/2026-10-25">← October 25</a>
    <span class="diary-footer-meta">Generated Oct 26, 2026, 9:04 AM ET</span>
    <a class="diary-footer-next" href="/diary/2026-10-27">October 27 →</a>
  </footer>
</div>"""


def _listing(options: dict) -> str:
    return "\n".join(f"- {k}: {v}" for k, v in options.items())


@cache
def base_stylesheet() -> str:
    """The site's own diary rules, read from the site so the prompt can't drift from them."""
    text = GLOBALS_CSS.read_text()
    start, end = text.index("/* diary:start */"), text.index("/* diary:end */")
    return textwrap.dedent(text[start + len("/* diary:start */"):end]).strip()


@cache
def prompt() -> str:
    return f"""You are the art director of Daily World Diary, a news digest written fresh every morning. Every day's page gets its own visual identity, and you design it: you read the whole edition, decide how the page is built, and write the stylesheet that makes it look like that day and no other.

# The brief
- The design comes from the content. Find the day's dominant mood and its biggest story, and let them decide everything: the structure, the palette, the type, the ornament. A reader who knows what happened that day should recognise it in the design.
- Every day must look clearly different. Readers open this page every morning, so two days that look alike are a failure even if both are handsome. You'll be shown the last few days' designs; change the structure as well as the colours, not just one of them.
- Be bold. The base stylesheet below is a neutral scaffold, not a style to imitate: a design that keeps its warm paper, its serif headline and its plain columns has not done the job. Push hard on at least two of: the palette (dark, saturated, monochrome, high-key...), the type (scale, weight, case, tracking), the structure (header style, card mix, layouts) and the ornament (rules, borders, shadows, gradients, rotated labels, oversized numerals, patterns made with gradients).
- Translate the mood instead of illustrating it literally. No flag colours for an election, no automatic red for a bad day. Ask what the day felt like (tense, relieved, feverish, uncertain, celebratory, sombre) and design that.
- Reading still comes first. Body text stays comfortable on a 360px phone and on a wide monitor: 16-20px, line-height 1.5-1.8, and no more than about 75 characters per line.
- Headlines must fit a 360px phone: the longest word of the headline ("OCTOBER", "DIGEST") has to fit on one line, so with wide or uppercase display fonts keep the phone size around 2.25-2.75rem and scale up from there.
- Motion is optional and restrained: at most one subtle entrance or hover effect, nothing that loops forever over text.

# How the page is built
You choose the structure from these components; the site renders them, and your CSS styles them.

Header style (one for the page):
{_listing(HEROES)}

Card components (one per section; every story in that section uses it):
{_listing(CARDS)}

Layouts (one per section; how its cards are arranged):
{_listing(LAYOUTS)}

Match the choice to the material: a section with many short stories suits a grid, a rail or masonry; one with two long stories suits stack or split; market sections suit stat cards. You're told how many stories each section has.

Variety rules (checked):
- Use at least {MIN_CARDS} different card components and at least {MIN_LAYOUTS} different layouts on the page.
- Use a different header style and a different --font-display family from the previous day's design.

# The page markup
The structure is fixed apart from your choices; you only write CSS for it. data-hero, data-card and data-layout carry your choices, so you can target them, and each section can be targeted with [data-section="..."]:

{PAGE}

# The base stylesheet you are layering over
It lays out the page, every header style, card and layout, all drawn from the design tokens. At 1024px and wider the contents sit in a sticky left column; below that they become a sticky horizontal strip at the top of the screen, and grids collapse to one column on phones.

Your CSS loads after it and wins property by property, but every property you don't override still applies. Check what the base gives an element before you restyle it: if you change an element's text colour, look at the background the base gives it (and the other way round), so you never end up with text the same colour as its background. Keep the page working at every width: the contents must stay reachable on phones.

```css
{base_stylesheet()}
```

# Design tokens (required)
Your stylesheet must contain a plain `.diary-page {{ ... }}` rule (not inside @media) that sets all of these:
- --paper: page background
- --paper-alt: background of the header and of tiles and panels
- --ink: headlines and the strongest text
- --ink-soft: body text
- --muted: dates, labels and other secondary text
- --accent: the signature colour (numbers, kicker, banners, citation links, the active contents link)
- --accent-ink: text placed on an --accent background
- --rule: borders and dividers
- --font-display: headline font
- --font-body: body text font
- --font-ui: labels, contents, kicker, citations and footer font

Colour tokens must be 6-digit hex values such as #1f2a44. These contrast ratios are checked, on --paper and on --paper-alt alike:
- --ink: at least 7:1
- --ink-soft, --muted and --accent: at least 4.5:1
- --accent-ink on --accent: at least 4.5:1
Set these tokens only in .diary-page rules; redefining them on any other element is rejected.
Aim for 5:1 or more on the 4.5:1 pairs so you aren't caught by rounding, and remember --paper-alt is usually the harder background.
If you also redefine tokens inside a media query (a dark-mode version, for example), the redefined set is checked the same way. You may use other colours elsewhere (gradients, ornaments, borders, section tints). Text you colour with anything other than a token is checked too: it needs 4.5:1 on --paper and --paper-alt in every colour scheme it applies to, so a colour picked for light paper must be redefined for a dark scheme (put it in a custom property on .diary-page and redefine that in the media query). A rule that sets its own background is exempt, so make sure its text reads on that background yourself.
Citation links can be long: never stop them wrapping.
Don't set colours with a universal selector (e.g. `.diary-hero *`): it outranks your own, more specific rules for the elements inside.

These fonts are loaded. Use them only through their variables, always with a generic fallback, for example `var(--ff-syne), sans-serif`:
{_listing({f"var({k})": v for k, v in FONTS.items()})}
No other fonts are available.

# Hard rules: a design that breaks any of them is rejected
1. It starts with exactly these two comments:
   /* theme: <name, 2-5 words> | <one sentence of 10-200 characters on how the design reflects the day> */
   /* layout: hero=<header style>; <section id>=<card>/<layout>; <section id>=<card>/<layout>; ... */
   The layout comment names every section on the page, e.g. `hero=poster; political-news=banner/grid-2; financial-news=stat/grid-3`. Readers see the theme name and sentence on the page, so write them for readers, not for a developer.
2. Every selector starts with .diary-page, e.g. `.diary-page .diary-title` or `.diary-page [data-card="stat"] .diary-card-figure`.
3. Nothing that loads a resource: no url(), image(), image-set(), @import or @font-face. For ornament use gradients, borders, shadows, and ::before/::after with string content.
4. The only at-rules allowed are @media, @supports, @container and @keyframes. .diary-article (named "article") and every .diary-card are size containers, so @container queries work inside them.
5. No "<" characters and no backslashes anywhere.
6. Never hide content (no display: none or visibility: hidden, except on your own ::before/::after ornaments) and never use position: fixed.
7. Under {MAX_CSS:,} characters in total.

# Output
Reply with the two comments followed by the CSS: no Markdown fences, no explanation before or after."""


def stories(md: str) -> int:
    """How many cards a section's markdown becomes: one per ### heading, plus any text before the first."""
    headings = len(re.findall(r"^### ", md, re.M))
    lead = md.split("\n### ")[0].strip()
    return headings + (1 if lead and not lead.startswith("### ") else 0) or 1


def describe(day: str, theme: dict) -> str:
    """One line on a past day's design, for the prompt."""
    tokens: dict = {}
    try:
        _rules(tinycss2.parse_stylesheet(theme["css"], skip_comments=True, skip_whitespace=True), tokens, [])
    except ValueError:
        pass
    palette = ", ".join(f"{t} {tokens[t]}" for t in ("--paper", "--ink", "--accent") if t in tokens)
    fonts = ", ".join(f"{t} {m[1]}" for t in ("--font-display", "--font-body")
                      if (m := FONT_VAR.search(tokens.get(t, ""))))
    picks = "; ".join(f"{sid}={p['card']}/{p['layout']}" for sid, p in theme.get("sections", {}).items())
    parts = [f'{day} "{theme["name"]}": {theme["note"]}', f"header {theme.get('hero', 'classic')}",
             palette, fonts, picks]
    return "- " + " | ".join(p for p in parts if p)


def recent(date: str) -> list[tuple[str, dict]]:
    """(date, theme) for the latest HISTORY_DAYS entries before `date` that have one, newest first."""
    out = []
    for day in reversed([d for d in store.list_dates() if d < date]):
        theme = (store.read(day) or {}).get("theme")
        if theme:
            out.append((day, theme))
        if len(out) == HISTORY_DAYS:
            break
    return out


def context(date: str, title: str, summary: str, sections: list[tuple[str, str, str]],
            history: list[tuple[str, dict]]) -> str:
    """sections: (section id, title, markdown) in page order."""
    d = Date.fromisoformat(date)
    listing = "\n".join(f"- {sid}: {title_}, {n} {'story' if n == 1 else 'stories'}"
                        for sid, title_, md in sections for n in [stories(md)])
    past = "\n".join(describe(day, theme) for day, theme in history) or "- none yet"
    body = "\n\n".join(f"## {title_}\n\n{md}" for _, title_, md in sections)
    return (f"Design the page for {d:%A}, {d:%B} {d.day}, {d.year}.\n\n"
            f"Headline: {title}\n\nSummary shown under the headline: {summary}\n\n"
            f"Sections on the page, in order (use these ids in the layout comment):\n{listing}\n\n"
            f"The most recent designs, newest first. Today's must look clearly different from all of them, "
            f"and its header style and --font-display must differ from the first one:\n{past}\n\n"
            f"The full edition follows. Read all of it before you decide on a direction.\n\n{body}")


def _luminance(hex_: str) -> float:
    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(int(hex_[i:i + 2], 16) / 255) for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _walk(tokens):
    """Every component value, nested function arguments and blocks included."""
    for t in tokens:
        yield t
        if t.type == "function":
            yield from _walk(t.arguments)
        elif t.type in ("() block", "[] block", "{} block"):
            yield from _walk(t.content)


def _selectors(prelude) -> list[str]:
    groups, current = [], []
    for t in prelude:
        if t.type == "literal" and t.value == ",":
            groups.append(current)
            current = []
        else:
            current.append(t)
    groups.append(current)
    return [tinycss2.serialize(g).strip() for g in groups]


def _declarations(content, where: str, ornament: bool = False) -> list:
    decls = []
    for d in tinycss2.parse_blocks_contents(content, skip_comments=True, skip_whitespace=True):
        if d.type == "error":
            raise ValueError(f"CSS error in {where} (line {d.source_line}): {d.message}")
        if d.type != "declaration":
            raise ValueError(f"nested rules are not allowed (in {where}, line {d.source_line})")
        for t in _walk(d.value):
            if t.type == "url" or (t.type == "function" and t.lower_name in BANNED_FUNCTIONS):
                raise ValueError(f"{d.name} in {where} uses a resource function; nothing may load external resources")
        value = tinycss2.serialize(d.value).strip().lower()
        if d.lower_name == "position" and "fixed" in value:
            raise ValueError(f"position: fixed is not allowed (in {where})")
        # hiding a ::before/::after ornament is fine; hiding real content is not
        if not ornament and \
                ((d.lower_name == "display" and value.startswith("none")) or
                 (d.lower_name == "visibility" and value.startswith(("hidden", "collapse")))):
            raise ValueError(f"{d.name}: {value} hides content (in {where})")
        decls.append(d)
    return decls


def _rules(rules, tokens: dict, variants: list, where: str | None = None, literals: list | None = None) -> None:
    """Checks every rule. Tokens set by a plain top-level .diary-page rule go in `tokens`; a
    .diary-page rule inside an at-rule (a dark mode, say) is a variant, checked separately. Text
    colours set to anything but a design token go in `literals`, checked once the tokens are known."""
    for r in rules:
        if r.type == "error":
            raise ValueError(f"CSS parse error (line {r.source_line}): {r.message}")
        if r.type == "at-rule":
            if r.lower_at_keyword not in AT_RULES:
                raise ValueError(f"@{r.lower_at_keyword} is not allowed; only "
                                 + ", ".join(f"@{a}" for a in sorted(AT_RULES)))
            if r.content is None:
                raise ValueError(f"@{r.lower_at_keyword} needs a {{ }} block")
            inner = tinycss2.parse_rule_list(r.content, skip_comments=True, skip_whitespace=True)
            if r.lower_at_keyword == "keyframes":
                for frame in inner:
                    if frame.type != "qualified-rule":
                        raise ValueError(f"bad keyframe in @keyframes (line {r.source_line})")
                    _declarations(frame.content, "@keyframes")
            else:
                label = f"@{r.lower_at_keyword} {tinycss2.serialize(r.prelude).strip()}"
                _rules(inner, tokens, variants, f"{where} {label}" if where else label, literals)
        elif r.type == "qualified-rule":
            selectors = _selectors(r.prelude)
            for s in selectors:
                if not SCOPE.match(s):
                    raise ValueError(f'selector "{s}" must start with .diary-page')
            decls = _declarations(r.content, ", ".join(selectors), all(ORNAMENT.search(s) for s in selectors))
            if selectors != [".diary-page"]:
                # 2026-10-22: --accent redefined on the poster header slipped past every contrast check
                redefined = [d.name for d in decls if d.lower_name in COLOR_TOKENS + FONT_TOKENS]
                if redefined:
                    raise ValueError(f"{', '.join(redefined)} can only be set in a .diary-page rule, "
                                     f"not in {', '.join(selectors)}")
            # 2026-10-22: `.diary-hero * { color }` outranked the theme's own badge rule and painted
            # the badge text the colour of its background
            wild = [s for s in selectors if UNIVERSAL.search(s)]
            if wild and any(d.lower_name in ("color", "background", "background-color") for d in decls):
                raise ValueError(f'"{wild[0]}" sets a colour on every element below it, which outranks your more '
                                 "specific rules; colour elements by their class instead")
            if literals is not None and not any(d.lower_name in ("background", "background-color") for d in decls):
                literals += [(where, ", ".join(selectors), tinycss2.serialize(d.value).strip())
                             for d in decls if d.lower_name == "color"]
            if selectors == [".diary-page"]:
                values = {d.lower_name: tinycss2.serialize(d.value).strip() for d in decls}
                if where is None:
                    tokens.update(values)
                else:
                    variants.append((where, values))


def _layout(spec: str, section_ids: list[str]) -> tuple[str, dict]:
    """`hero=x; id=card/layout; ...` -> (hero, {id: {"card", "layout"}})."""
    picks = {}
    for part in filter(None, (p.strip() for p in spec.split(";"))):
        key, _, value = (s.strip() for s in part.partition("="))
        if not value:
            raise ValueError(f'"{part}" in the layout comment is not key=value')
        picks[key] = value
    hero = picks.pop("hero", None)
    if hero not in HEROES:
        raise ValueError(f"the layout comment needs hero=<{'|'.join(HEROES)}>, got {hero!r}")
    unknown = [k for k in picks if k not in section_ids]
    if unknown:
        raise ValueError(f"the layout comment names sections that aren't on the page: {', '.join(unknown)}")
    missing = [s for s in section_ids if s not in picks]
    if missing:
        raise ValueError(f"the layout comment must give a card/layout for {', '.join(missing)}")
    sections = {}
    for sid in section_ids:
        card, _, layout = (s.strip() for s in picks[sid].partition("/"))
        if card not in CARDS:
            raise ValueError(f"{sid}: card {card!r} is not one of {', '.join(CARDS)}")
        if layout not in LAYOUTS:
            raise ValueError(f"{sid}: layout {layout!r} is not one of {', '.join(LAYOUTS)}")
        sections[sid] = {"card": card, "layout": layout}
    cards = {p["card"] for p in sections.values()}
    layouts = {p["layout"] for p in sections.values()}
    if len(cards) < min(MIN_CARDS, len(sections)):
        raise ValueError(f"use at least {MIN_CARDS} different card components; you used {', '.join(sorted(cards))}")
    if len(layouts) < min(MIN_LAYOUTS, len(sections)):
        raise ValueError(f"use at least {MIN_LAYOUTS} different layouts; you used {', '.join(sorted(layouts))}")
    return hero, sections


def validate(raw: str, section_ids: list[str], previous: dict | None = None) -> dict:
    """The model's reply -> {"name", "note", "hero", "sections", "css"}. `previous` is the latest
    earlier day's theme, which today's must differ from. Raises ValueError saying what to fix."""
    css = raw.strip()
    if m := FENCE.match(css):
        css = m["css"].strip()
    if not css:
        raise ValueError("the reply was empty")
    if len(css) > MAX_CSS:
        raise ValueError(f"the stylesheet is {len(css):,} characters; the limit is {MAX_CSS:,}")
    if "<" in css or "\\" in css:
        raise ValueError('the stylesheet contains "<" or a backslash, which are not allowed')
    header = HEADER.match(css)
    if not header:
        raise ValueError("the reply must start with /* theme: <name> | <one sentence> */ "
                         "followed by /* layout: hero=...; <section id>=<card>/<layout>; ... */")
    hero, sections = _layout(header["layout"], section_ids)

    tokens: dict[str, str] = {}
    variants: list[tuple[str, dict]] = []
    literals: list[tuple[str | None, str, str]] = []
    _rules(tinycss2.parse_stylesheet(css, skip_comments=True, skip_whitespace=True), tokens, variants,
           literals=literals)

    missing = [t for t in COLOR_TOKENS + FONT_TOKENS if t not in tokens]
    if missing:
        raise ValueError(f"the plain .diary-page rule (outside any @media) must set {', '.join(missing)}")
    # one colour scheme may be split over several blocks with the same condition
    merged: dict[str, dict] = {}
    for where, values in variants:
        merged.setdefault(where, {}).update(values)
    variants = list(merged.items())
    _check_colors(tokens, "")
    for where, values in variants:
        _check_colors({**tokens, **values}, f" inside {where}")
    _check_literals(literals, tokens, variants)

    if previous:
        if hero == previous.get("hero", "classic"):
            raise ValueError(f"the previous day also used hero={hero}; pick a different header style")
        before: dict = {}
        try:
            _rules(tinycss2.parse_stylesheet(previous["css"], skip_comments=True, skip_whitespace=True), before, [])
        except ValueError:
            pass
        today_font, last_font = (FONT_VAR.search(t.get("--font-display", "")) for t in (tokens, before))
        if today_font and last_font and today_font[1] == last_font[1]:
            raise ValueError(f"the previous day also used {today_font[1]} for --font-display; pick another")
    return {"name": header["name"].strip(), "note": header["note"].strip(), "hero": hero,
            "sections": sections, "css": css}


def _check_literals(literals: list, tokens: dict, variants: list) -> None:
    """A text colour that isn't a design token must be readable on --paper and --paper-alt in every
    colour scheme it applies to: 2026-10-25's green chart labels were fine on light paper and 2.9:1
    in dark mode. A rule that also sets its own background is left alone."""
    for where, selector, value in literals:
        var = re.fullmatch(r"var\((--[\w-]+)\)", value)
        if var and var[1] in COLOR_TOKENS:
            continue  # the token pairs are checked already
        schemes = [(f" inside {w}", {**tokens, **v}) for w, v in variants if where is None or w == where]
        if where is None or not schemes:
            schemes.insert(0, ("", tokens))
        for label, t in schemes:
            hex_ = t.get(var[1], "") if var else value
            if not HEX.match(hex_):
                continue  # a keyword or function we can't measure; currentColor and friends
            for bg in ("--paper", "--paper-alt"):
                if HEX.match(t[bg]) and (ratio := contrast(hex_, t[bg])) < 4.5:
                    raise ValueError(f"{selector} sets color {value}, which is {ratio:.2f}:1 on {bg}{label}; "
                                     "text needs 4.5:1 on every background and colour scheme. Use a token, "
                                     "or a colour that works in each scheme")


def _check_colors(tokens: dict, where: str) -> None:
    bad = [t for t in COLOR_TOKENS if not HEX.match(tokens[t])]
    if bad:
        raise ValueError(f"{', '.join(f'{t} ({tokens[t]})' for t in bad)}{where} must be 6-digit hex colours")
    low = [f"{fg} on {bg} is {ratio:.2f}:1, needs {need}:1" for fg, bg, need in CONTRAST
           if (ratio := contrast(tokens[fg], tokens[bg])) < need]
    if low:
        raise ValueError(f"contrast too low{where}: " + "; ".join(low))


async def run_design(date: str, title: str, summary: str,
                     sections: list[tuple[str, str, str]]) -> tuple[dict | None, dict]:
    """-> (theme or None, usage summed over every attempt). Never raises on a bad design or a
    provider error: a day without a theme still gets the base design."""
    history = recent(date)
    previous = history[0][1] if history else None
    section_ids = [sid for sid, _, _ in sections]
    messages = [{"role": "system", "content": prompt()},
                {"role": "user", "content": context(date, title, summary, sections, history)}]
    usage: dict = {}
    for attempt in range(1 + MAX_RETRIES):
        try:
            resp = await client().chat.completions.create(
                model=model(),
                messages=messages,
                max_tokens=MAX_TOKENS,
                extra_headers={"X-Title": "Daily World Diary"},
                # same reason as the agents: reasoning tokens can eat the budget and return nothing
                extra_body={"reasoning": {"enabled": False}},
            )
        except openai.APIStatusError as e:
            if e.status_code in ACCOUNT_STATUSES:
                log.warning("design: OpenRouter rejected the key (%s); no theme", e.status_code)
                return None, usage
            log.warning("design attempt %d failed: %s", attempt + 1, e)
            continue
        except openai.APIError as e:
            log.warning("design attempt %d failed: %s", attempt + 1, e)
            continue

        for k, v in (resp.usage.model_dump() if resp.usage else {}).items():
            if isinstance(v, (int, float)):
                usage[k] = usage.get(k, 0) + v
        choice = resp.choices[0]
        reply = choice.message.content or ""
        try:
            if choice.finish_reason == "length":
                raise ValueError(f"the stylesheet was cut off at {MAX_TOKENS:,} tokens; write a shorter one")
            theme = validate(reply, section_ids, previous)
        except ValueError as e:
            log.warning("design attempt %d rejected: %s", attempt + 1, e)
            messages += [{"role": "assistant", "content": reply},
                         {"role": "user", "content": f"That design was rejected: {e}. "
                                                     "Reply with the complete corrected design only: "
                                                     "both comments and the whole stylesheet."}]
            continue
        log.info("design: %r after %d attempt(s)", theme["name"], attempt + 1)
        return theme, usage
    log.warning("design: no valid design after %d attempts; using the base design", 1 + MAX_RETRIES)
    return None, usage
