"""The day's look: one last model call reads the day's news and designs its page.

It names the day's mood, which fixes the colour family (a bad day is dark and red, a tragic one
blue, a good one light and green, a tense one amber, a neutral one white or black), picks a header
style and, for every section, one of ten card components and one of six layouts, then writes the
CSS on top. The CSS is injected into the page as-is, so it is treated as untrusted input: parsed,
scoped to .diary-page, stripped of anything that loads a resource, and checked for readable
contrast and for colours that match the mood. To keep days from looking alike, the model sees the
last few days' designs and the picks must vary. A rejected design goes back to the model with the
reason, up to MAX_RETRIES times."""

import colorsys
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

# The day's mood sets the palette, so a reader can tell what kind of day it was at a glance.
# mood -> (when it applies, its colours, hue family or None for no colour, "light"/"dark"/None)
MOODS = {
    "good": ("the news is mostly good: relief, progress, recoveries, rallies, breakthroughs, celebrations",
             "a light page tinted green with a deep green accent, e.g. --paper #e1f2e5, --accent #11652f",
             "green", "light"),
    "bad": ("things are going badly: escalating conflict, crises, crashes, scandals, failures",
            "a dark page tinted red with a bright red accent, e.g. --paper #1c0b0d, --accent #ff5c5c",
            "red", "dark"),
    "tragic": ("loss of life dominates: deadly disasters or attacks, the human toll of a war, a death "
               "that grieves many",
               "a page tinted blue, dark or light, with a blue accent, e.g. --paper #0c1626, --accent #7db4ff, "
               "or --paper #e7eef8, --accent #1f4f99", "blue", None),
    "tense": ("the world is on edge and waiting: standoffs, deadlines, pending votes or verdicts, "
              "markets bracing",
              "a page tinted amber, light or dark, with an amber or orange accent, e.g. --paper #fbf0d9, "
              "--accent #8f4000, or --paper #1d1607, --accent #ffad33", "amber", None),
    "neutral": ("no clear direction: a quiet day, or good and bad news that cancel out",
                "a plain white or near-black page with no tint and an uncoloured (black, white or grey) "
                "accent, e.g. --paper #fafafa, --accent #1a1a1a, or --paper #111111, --accent #ededed",
                None, None),
}
HUES = {"red": (340, 15), "amber": (18, 50), "green": (80, 165), "blue": (190, 250)}  # degrees; red wraps past 0
# how far apart a colour's strongest and weakest RGB channels (0-255) are: its amount of colour
TINTED, STRONG = 16, 80  # --paper/--paper-alt at least TINTED, --accent at least STRONG, in the mood's hue
GREY_PAPER, GREY_ACCENT = 6, 24  # neutral: at most this much colour
LIGHT, DARK = 0.7, 0.05  # relative luminance of --paper on light and dark pages

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
HEADER_BOX = re.compile(r"\.diary-hero(-inner)?$")  # a selector for the block behind the header's text
SCOPE = re.compile(r"^\.diary-page(?![\w-])")
FONT_VAR = re.compile(r"var\((--ff-[\w-]+)\)")
HEADER = re.compile(r"^/\*\s*theme:\s*(?P<name>[^|*]{2,60}?)\s*\|\s*(?P<note>[^*]{10,240}?)\s*\*/\s*"
                    r"/\*\s*mood:\s*(?P<mood>[^*]+?)\s*\*/\s*"
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
      <nav class="diary-crumbs"><a href="/">All editions</a></nav>
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
        <a class="diary-toc-bottom" href="#bottom">↓ Go to bottom</a>
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
                     In music-releases each Spotify citation is instead Spotify's own player:
                     <iframe class="diary-embed" height="152">. Players stand alone: a section with players
                     always renders plain cards, and the site strips any border, background, shadow or side
                     padding from a player and from the card, list and item holding it. Don't style them. -->
              </div>
            </div>
          </article>
        </div>
      </section>
      <!-- more sections -->
    </article>
  </div>
  <footer class="diary-footer" id="bottom">
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
    return f"""You are the art director of Daily World Diary, a news digest written fresh every morning. Every day's page gets its own visual identity, and you design it: you read the day's news, name its mood, decide how the page is built, and write the stylesheet that makes it look like that day and no other.

# The brief
- The day's news decides the colours. Before anything else, decide the day's mood: read the summary under the headline (the whole day in brief), skim the edition, and pick the one mood below that a reader would use to sum up the day. The mood fixes the page's colour family, and it must be unmistakable: someone glancing at the page should know at once whether it was a good, bad, tragic, tense or quiet day.
- The type, the ornament and the structure carry the rest of the day's feeling (feverish, sombre, relieved, defiant, uncertain...) within that colour family.
- The rest of the edition is for fitting the components to the material (how many stories each section has, how long they are, which carry figures).
- Every day must look clearly different. Readers open this page every morning, so two days that look alike are a failure even if both are handsome. You'll be shown the last few days' designs and their moods. Days with the same mood share a colour family, so make them differ in everything else: the header style, the card mix, the layouts, the type, the ornament and the exact shades.
- Be bold. The base stylesheet below is a neutral scaffold, not a style to imitate: a design that keeps its warm paper, its serif headline and its plain columns has not done the job. Push the mood's colours as far as they go, and push hard on at least one of: the type (scale, weight, case, tracking), the structure (header style, card mix, layouts) and the ornament (rules, borders, shadows, gradients, rotated labels, oversized numerals, patterns made with gradients).
- Reading still comes first. Body text stays comfortable on a 360px phone and on a wide monitor: 16-20px, line-height 1.5-1.8, and no more than about 75 characters per line.
- Headlines must fit a 360px phone: the longest word of the headline ("OCTOBER", "DIGEST") has to fit on one line, so with wide or uppercase display fonts keep the phone size around 2.25-2.75rem and scale up from there.
- Motion is optional and restrained: at most one subtle entrance or hover effect, nothing that loops forever over text.

# The mood and its colours (checked)
Pick exactly one mood:
{chr(10).join(f"- {mood}: {when}. Colours: {colours}." for mood, (when, colours, _, _) in MOODS.items())}

If one story dominates the day, it sets the mood. When good and bad news cancel out, the day is neutral, or tense if the world is waiting on something.

Your palette is checked against the mood. A colour's amount of colour is how far apart its strongest and weakest RGB channels are: #2a1013 has 26 (42 vs 16), #161414 has 2. Its hue must fall in the family: {", ".join(f"{family} {lo}-{hi}°" for family, (lo, hi) in HUES.items())}.
- good, bad, tragic and tense: --paper and --paper-alt are both tinted in the mood's hue (at least {TINTED}), and --accent is a strong colour of that hue (at least {STRONG}).
- good pages are light: --paper at relative luminance {LIGHT} or more. bad pages are dark: --paper at {DARK} or less.
- neutral pages have no colour: --paper and --paper-alt at most {GREY_PAPER} (white or near-black), --accent at most {GREY_ACCENT} (black, white or grey).
- Every set of tokens you write is checked, so don't add a dark-mode (prefers-color-scheme) version: the mood decides light or dark.
Keep the other colours you use (gradients, ornaments, borders, section tints) in the same family, so nothing contradicts the mood.

# How the page is built
You choose the structure from these components; the site renders them, and your CSS styles them.

Header style (one for the page):
{_listing(HEROES)}

Card components (one per section; every story in that section uses it):
{_listing(CARDS)}

Layouts (one per section; how its cards are arranged):
{_listing(LAYOUTS)}

Match the choice to the material: a section with many short stories suits a grid, a rail or masonry; one with two long stories suits stack or split; market sections suit stat cards. You're told how many stories each section has. Spotify players stand alone, never boxed, so music-releases always renders plain cards: pick plain for it.

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
If you also redefine tokens inside a media query, the redefined set is checked the same way, for contrast and for the mood. You may use other colours elsewhere (gradients, ornaments, borders, section tints), in the mood's family. Text you colour with anything other than a token is checked too: it needs 4.5:1 on --paper and --paper-alt in every colour scheme it applies to, so a colour picked for light paper must be redefined for a dark scheme (put it in a custom property on .diary-page and redefine that in the media query). A rule that sets its own background is exempt, so make sure its text reads on that background yourself. The header is checked, though: every colour in a background you give .diary-hero or .diary-hero-inner, gradient stops included, needs 4.5:1 with the header's text, which is --accent-ink on a poster header and --ink, --ink-soft, --muted and --accent on the others.
Citation links can be long: never stop them wrapping.
Don't set colours with a universal selector (e.g. `.diary-hero *`): it outranks your own, more specific rules for the elements inside.

These fonts are loaded. Use them only through their variables, always with a generic fallback, for example `var(--ff-syne), sans-serif`:
{_listing({f"var({k})": v for k, v in FONTS.items()})}
No other fonts are available.

# Hard rules: a design that breaks any of them is rejected
1. It starts with exactly these three comments:
   /* theme: <name, 2-5 words> | <one sentence of 10-200 characters on how the design reflects the day> */
   /* mood: <{"|".join(MOODS)}> */
   /* layout: hero=<header style>; <section id>=<card>/<layout>; <section id>=<card>/<layout>; ... */
   The layout comment names every section on the page, e.g. `hero=poster; political-news=banner/grid-2; financial-news=stat/grid-3`. Readers see the theme name and sentence on the page, so write them for readers, not for a developer.
2. Every selector starts with .diary-page, e.g. `.diary-page .diary-title` or `.diary-page [data-card="stat"] .diary-card-figure`.
3. Nothing that loads a resource: no url(), image(), image-set(), @import or @font-face. For ornament use gradients, borders, shadows, and ::before/::after with string content.
4. The only at-rules allowed are @media, @supports, @container and @keyframes. .diary-article (named "article") and every .diary-card are size containers, so @container queries work inside them.
5. No "<" characters and no backslashes anywhere.
6. Never hide content (no display: none or visibility: hidden, except on your own ::before/::after ornaments) and never use position: fixed.
7. Under {MAX_CSS:,} characters in total.

# Output
Reply with the three comments followed by the CSS: no Markdown fences, no explanation before or after."""


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
    parts = [f'{day} "{theme["name"]}": {theme["note"]}', theme.get("mood") and f"mood {theme['mood']}",
             f"header {theme.get('hero', 'classic')}", palette, fonts, picks]
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
            f"Headline: {title}\n\nSummary shown under the headline (the day in brief: decide the mood from it): "
            f"{summary}\n\n"
            f"Sections on the page, in order (use these ids in the layout comment):\n{listing}\n\n"
            f"The most recent designs, newest first. Today's must look clearly different from all of them, "
            f"and its header style and --font-display must differ from the first one:\n{past}\n\n"
            f"The full edition follows, for weighing the mood and for choosing each section's card and "
            f"layout.\n\n{body}")


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


def _rules(rules, tokens: dict, variants: list, where: str | None = None, literals: list | None = None,
           backgrounds: list | None = None) -> None:
    """Checks every rule. Tokens set by a plain top-level .diary-page rule go in `tokens`; a
    .diary-page rule inside an at-rule (a dark mode, say) is a variant, checked separately. Text
    colours set to anything but a design token go in `literals`, and backgrounds given to the header
    in `backgrounds`, both checked once the tokens are known."""
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
                _rules(inner, tokens, variants, f"{where} {label}" if where else label, literals, backgrounds)
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
            if backgrounds is not None and any(HEADER_BOX.search(s) for s in selectors):
                backgrounds += [(where, ", ".join(selectors), d.value) for d in decls
                                if d.lower_name in ("background", "background-color", "background-image")]
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
        raise ValueError("the reply must start with /* theme: <name> | <one sentence> */, then "
                         f"/* mood: <{'|'.join(MOODS)}> */, then "
                         "/* layout: hero=...; <section id>=<card>/<layout>; ... */")
    mood = header["mood"].lower()
    if mood not in MOODS:
        raise ValueError(f"the mood must be one of {', '.join(MOODS)}, got {header['mood']!r}")
    hero, sections = _layout(header["layout"], section_ids)

    tokens: dict[str, str] = {}
    variants: list[tuple[str, dict]] = []
    literals: list[tuple[str | None, str, str]] = []
    backgrounds: list = []
    _rules(tinycss2.parse_stylesheet(css, skip_comments=True, skip_whitespace=True), tokens, variants,
           literals=literals, backgrounds=backgrounds)

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
    _check_header(backgrounds, hero, tokens, variants)
    _check_mood(mood, tokens, "")
    for where, values in variants:
        _check_mood(mood, {**tokens, **values}, f" inside {where}")

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
    return {"name": header["name"].strip(), "note": header["note"].strip(), "mood": mood, "hero": hero,
            "sections": sections, "css": css}


def _check_literals(literals: list, tokens: dict, variants: list) -> None:
    """A text colour that isn't a design token must be readable on --paper and --paper-alt in every
    colour scheme it applies to: 2026-10-25's green chart labels were fine on light paper and 2.9:1
    in dark mode. A rule that also sets its own background is left alone."""
    for where, selector, value in literals:
        var = re.fullmatch(r"var\((--[\w-]+)\)", value)
        if var and var[1] in COLOR_TOKENS:
            continue  # the token pairs are checked already
        for label, t in _schemes(where, tokens, variants):
            hex_ = t.get(var[1], "") if var else value
            if not HEX.match(hex_):
                continue  # a keyword or function we can't measure; currentColor and friends
            for bg in ("--paper", "--paper-alt"):
                if HEX.match(t[bg]) and (ratio := contrast(hex_, t[bg])) < 4.5:
                    raise ValueError(f"{selector} sets color {value}, which is {ratio:.2f}:1 on {bg}{label}; "
                                     "text needs 4.5:1 on every background and colour scheme. Use a token, "
                                     "or a colour that works in each scheme")


def _schemes(where: str | None, tokens: dict, variants: list) -> list[tuple[str, dict]]:
    """(label, tokens) for every colour scheme a rule inside `where` (None: top level) applies in."""
    schemes = [(f" inside {w}", {**tokens, **v}) for w, v in variants if where is None or w == where]
    if where is None or not schemes:
        schemes.insert(0, ("", tokens))
    return schemes


def _check_header(backgrounds: list, hero: str, tokens: dict, variants: list) -> None:
    """A background the theme gives the header must keep the header's text readable on every colour
    in it, gradient stops included: 2026-10-23's poster faded from its bright --accent to near-black
    under --accent-ink text. Colours that aren't hex or a hex custom property can't be measured."""
    text = ("--accent-ink",) if hero == "poster" else ("--ink", "--ink-soft", "--muted", "--accent")
    for where, selector, value in backgrounds:
        for label, t in _schemes(where, tokens, variants):
            for v in _walk(value):
                if v.type == "hash":
                    stop = f"#{v.value}"
                elif v.type == "function" and v.lower_name == "var" and v.arguments:
                    stop = t.get(tinycss2.serialize(v.arguments).split(",")[0].strip(), "")
                else:
                    continue
                for fg in text:
                    if HEX.match(stop) and (ratio := contrast(t[fg], stop)) < 4.5:
                        raise ValueError(f"{selector} puts {stop} behind the header, where its text ({fg} {t[fg]}) "
                                         f"is {ratio:.2f}:1{label}; header text needs 4.5:1 on every colour of "
                                         "its background, gradients included")


def _colour(hex_: str) -> tuple[float, int]:
    """(hue in degrees, amount of colour: how far apart the strongest and weakest RGB channels are)"""
    r, g, b = (int(hex_[i:i + 2], 16) for i in (1, 3, 5))
    return colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)[0] * 360, max(r, g, b) - min(r, g, b)


def _check_mood(mood: str, tokens: dict, where: str) -> None:
    """The mood's colours: --paper and --paper-alt tinted in its hue and --accent strongly in it, or
    no colour at all for neutral, and light or dark pages where the mood says so."""
    _, _, family, shade = MOODS[mood]
    wrong = []
    for t in ("--paper", "--paper-alt", "--accent"):
        hue, amount = _colour(tokens[t])
        if family is None:
            limit = GREY_ACCENT if t == "--accent" else GREY_PAPER
            if amount > limit:
                wrong.append(f"{t} {tokens[t]} has {amount} of colour, at most {limit} allowed")
        else:
            lo, hi = HUES[family]
            need = STRONG if t == "--accent" else TINTED
            if amount < need or not (lo <= hue <= hi if lo < hi else hue >= lo or hue <= hi):
                wrong.append(f"{t} {tokens[t]} is hue {hue:.0f}° with {amount} of colour; {family} needs "
                             f"{lo}-{hi}° and at least {need}")
        # only the page background: 2026-10-28's designer, also held to it on --paper-alt, traded tint
        # for lightness on the header until it gave up; contrast with --ink keeps the header close anyway
        lum = _luminance(tokens[t])
        if t == "--paper" and (shade == "light" and lum < LIGHT or shade == "dark" and lum > DARK):
            wrong.append(f"{t} {tokens[t]} has luminance {lum:.2f}, but a {mood} page is {shade} "
                         f"(light: at least {LIGHT}, dark: at most {DARK})")
    if wrong:
        raise ValueError(f"the colours don't match the {mood} mood{where}: " + "; ".join(wrong))


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
