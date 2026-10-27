"""The day's look: one last model call reads the finished entry and writes the CSS for its page.

The CSS is injected into the page as-is, so it is treated as untrusted input: parsed, scoped to
.diary-page, stripped of anything that loads a resource, and checked for readable contrast. A
rejected stylesheet goes back to the model with the reason, up to MAX_RETRIES times."""

import logging
import re
import textwrap
from datetime import date as Date
from functools import cache
from pathlib import Path

import openai
import tinycss2

from .agent import client, model

log = logging.getLogger(__name__)

MAX_RETRIES = 5  # retries after the first attempt
MAX_TOKENS = 12000
MAX_CSS = 20000
ACCOUNT_STATUSES = {401, 402, 403}  # retrying a rejected key only burns time

COLOR_TOKENS = ("--paper", "--paper-alt", "--ink", "--ink-soft", "--muted", "--accent", "--accent-ink", "--rule")
FONT_TOKENS = ("--font-display", "--font-body", "--font-ui")
# (foreground, background, minimum WCAG contrast ratio)
# the header (kicker, crumbs, theme note) sits on --paper-alt, the article on --paper
CONTRAST = (("--ink", "--paper", 7), ("--ink", "--paper-alt", 7),
            ("--ink-soft", "--paper", 4.5), ("--ink-soft", "--paper-alt", 4.5),
            ("--muted", "--paper", 4.5), ("--muted", "--paper-alt", 4.5),
            ("--accent", "--paper", 4.5), ("--accent", "--paper-alt", 4.5),
            ("--accent-ink", "--accent", 4.5))
AT_RULES = {"media", "supports", "keyframes"}
BANNED_FUNCTIONS = {"url", "image", "image-set", "-webkit-image-set", "cross-fade", "element", "expression",
                    "src", "paint", "env", "attr"}
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
ORNAMENT = re.compile(r"::?(before|after|marker)\b")
SCOPE = re.compile(r"^\.diary-page(?![\w-])")
HEADER = re.compile(r"^/\*\s*theme:\s*(?P<name>[^|*]{2,60}?)\s*\|\s*(?P<note>[^*]{10,240}?)\s*\*/")
FENCE = re.compile(r"^```[a-z]*\s*\n(?P<css>.*?)\n```$", re.S)
GLOBALS_CSS = Path(__file__).resolve().parents[2] / "website" / "src" / "app" / "globals.css"

# Mirrors website/src/app/diary/[date]/page.tsx and TableOfContents.tsx: keep the two in step.
PAGE = """<div class="diary-page" id="top" data-date="2026-10-26">
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
          <li><a class="diary-toc-link" href="#financial-news"><span class="diary-toc-number">02</span> Financial News</a></li>
          <!-- one per section; .is-active marks the section being read -->
        </ol>
        <a class="diary-toc-top" href="#top">↑ Back to top</a>
      </nav>
    </aside>
    <article class="diary-article">
      <section class="diary-section" id="political-news" data-section="political-news">
        <header class="diary-section-head">
          <span class="diary-section-number">01</span>
          <h2 class="diary-section-title">Political News</h2>
        </header>
        <div class="diary-prose">
          <!-- the section's body: only h3, h4, p, ul, ol, li, strong, em, blockquote, code, pre, hr, br -->
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

FONTS = """- var(--ff-fraunces): Fraunces, a soft, high-contrast display serif (variable weight 300-900)
- var(--ff-playfair): Playfair Display, a classic, dramatic didone serif for headlines
- var(--ff-newsreader): Newsreader, a serif designed for long reading at text sizes
- var(--ff-inter): Inter, a neutral, highly legible sans-serif
- var(--ff-space-grotesk): Space Grotesk, a geometric sans with a technical, contemporary edge
- var(--ff-plex-mono): IBM Plex Mono, a monospace (weights 400 and 600)
- var(--ff-bebas): Bebas Neue, an all-caps condensed display face (headlines only, never body text)"""

@cache
def base_stylesheet() -> str:
    """The site's own diary rules, read from the site so the prompt can't drift from them."""
    text = GLOBALS_CSS.read_text()
    start, end = text.index("/* diary:start */"), text.index("/* diary:end */")
    return textwrap.dedent(text[start + len("/* diary:start */"):end]).strip()


@cache
def prompt() -> str:
    return f"""You are the art director of Daily World Diary, a news digest written fresh every morning. Every day's page gets its own visual identity, and you design it: you read the whole edition and write the stylesheet that makes the page look like that day.

# What a good design does
- It comes from the content. Find the day's dominant mood and its biggest story, and let them decide the palette, the type pairing and the details. A reader who knows what happened that day should recognise it in the design.
- It is editorial: think of a great magazine cover or a newspaper's special edition. One strong idea carried through the whole page beats many small effects.
- It translates the mood instead of illustrating it literally. No flag colours for an election, no automatic red for a bad day. Ask what the day felt like (tense, relieved, feverish, uncertain, celebratory, sombre) and design that.
- Reading comes first. Sections are long, so body text must stay comfortable on a 360px phone and on a wide monitor: 17-20px, line-height 1.6-1.8, about 60-75 characters per line.
- Motion is optional and restrained: at most one subtle entrance or hover effect, nothing that loops forever over text.

# The page you are styling
The structure is fixed; you only write CSS for it:

{PAGE}

Each section can be targeted on its own with [data-section="..."]; today's sections are listed with the edition below.

# The base stylesheet you are layering over
This is how the page looks before your CSS. It lays the page out as a two-column grid at 1024px and wider (contents on the left, article on the right) and a single column below that, where the contents become a sticky horizontal strip at the top of the screen. Everything is drawn from the design tokens.

Your CSS loads after it and wins property by property, but every property you don't override still applies. Check what the base gives an element before you restyle it: if you change an element's text colour, look at the background the base gives it (and the other way round), so you never end up with text the same colour as its background. Keep the page working at every width: the contents must stay reachable on phones.

```css
{base_stylesheet()}
```

# Design tokens (required)
Your stylesheet must contain a plain `.diary-page {{ ... }}` rule (not inside @media) that sets all of these. They alone already restyle the whole page coherently; the rest of your CSS adds the day's character.
- --paper: page background
- --paper-alt: background of the header area and panels
- --ink: headlines and the strongest text
- --ink-soft: body text
- --muted: dates, labels and other secondary text
- --accent: the signature colour (section numbers, kicker, active contents link, ornaments)
- --accent-ink: text placed on an --accent background
- --rule: borders and dividers
- --font-display: headline font
- --font-body: body text font
- --font-ui: labels, contents, kicker and footer font

Colour tokens must be 6-digit hex values such as #1f2a44. These contrast ratios are checked, on --paper and on --paper-alt alike because the header sits on --paper-alt:
- --ink: at least 7:1
- --ink-soft, --muted and --accent: at least 4.5:1
- --accent-ink on --accent: at least 4.5:1
If you also redefine tokens inside a media query (a dark-mode version, for example), the redefined set is checked the same way.
You may use other colours elsewhere (gradients, ornaments, borders, section tints), but any text you colour yourself must stay just as readable.

These fonts are loaded. Use them only through their variables, always with a generic fallback, for example `var(--ff-fraunces), serif`:
{FONTS}
No other fonts are available.

# Hard rules: a stylesheet that breaks any of them is rejected
1. It starts with exactly one comment: /* theme: <name, 2-5 words> | <one sentence of 10-200 characters on how the design reflects the day> */
   Readers see both on the page, so write them for readers, not for a developer.
2. Every selector starts with .diary-page, e.g. `.diary-page .diary-title` or `.diary-page [data-section="music-releases"] h3`.
3. Nothing that loads a resource: no url(), image(), image-set(), @import or @font-face. For ornament use gradients, borders, shadows, and ::before/::after with string content.
4. The only at-rules allowed are @media, @supports and @keyframes.
5. No "<" characters and no backslashes anywhere.
6. Never hide content (no display: none or visibility: hidden, except on your own ::before/::after ornaments) and never use position: fixed.
7. Under {MAX_CSS:,} characters in total.

# Output
Reply with the CSS only: no Markdown fences, no explanation before or after."""


def context(date: str, title: str, summary: str, sections: list[tuple[str, str, str]]) -> str:
    """sections: (section id, title, markdown) in page order."""
    d = Date.fromisoformat(date)
    listing = "\n".join(f'- {title_} (data-section="{sid}")' for sid, title_, _ in sections)
    body = "\n\n".join(f"## {title_}\n\n{md}" for _, title_, md in sections)
    return (f"Design the page for {d:%A}, {d:%B} {d.day}, {d.year}.\n\n"
            f"Headline: {title}\n\nSummary shown under the headline: {summary}\n\n"
            f"Sections on the page, in order:\n{listing}\n\n"
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


def _rules(rules, tokens: dict, variants: list, where: str | None = None) -> None:
    """Checks every rule. Tokens set by a plain top-level .diary-page rule go in `tokens`; a
    .diary-page rule inside @media/@supports (a dark mode, say) is a variant, checked separately."""
    for r in rules:
        if r.type == "error":
            raise ValueError(f"CSS parse error (line {r.source_line}): {r.message}")
        if r.type == "at-rule":
            if r.lower_at_keyword not in AT_RULES:
                raise ValueError(f"@{r.lower_at_keyword} is not allowed; only @media, @supports and @keyframes")
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
                _rules(inner, tokens, variants, f"{where} {label}" if where else label)
        elif r.type == "qualified-rule":
            selectors = _selectors(r.prelude)
            for s in selectors:
                if not SCOPE.match(s):
                    raise ValueError(f'selector "{s}" must start with .diary-page')
            decls = _declarations(r.content, ", ".join(selectors), all(ORNAMENT.search(s) for s in selectors))
            if selectors == [".diary-page"]:
                values = {d.lower_name: tinycss2.serialize(d.value).strip() for d in decls}
                if where is None:
                    tokens.update(values)
                else:
                    variants.append((where, values))


def validate(raw: str) -> dict:
    """The model's reply -> {"name", "note", "css"}. Raises ValueError saying what to fix."""
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
        raise ValueError("the stylesheet must start with /* theme: <name> | <one sentence> */")

    tokens: dict[str, str] = {}
    variants: list[tuple[str, dict]] = []
    _rules(tinycss2.parse_stylesheet(css, skip_comments=True, skip_whitespace=True), tokens, variants)

    missing = [t for t in COLOR_TOKENS + FONT_TOKENS if t not in tokens]
    if missing:
        raise ValueError(f"the plain .diary-page rule (outside any @media) must set {', '.join(missing)}")
    _check_colors(tokens, "")
    for where, values in variants:
        _check_colors({**tokens, **values}, f" inside {where}")
    return {"name": header["name"].strip(), "note": header["note"].strip(), "css": css}


def _check_colors(tokens: dict, where: str) -> None:
    bad = [t for t in COLOR_TOKENS if not HEX.match(tokens[t])]
    if bad:
        raise ValueError(f"{', '.join(f'{t} ({tokens[t]})' for t in bad)}{where} must be 6-digit hex colours")
    low = [f"{fg} on {bg} is {ratio:.1f}:1, needs {need}:1" for fg, bg, need in CONTRAST
           if (ratio := contrast(tokens[fg], tokens[bg])) < need]
    if low:
        raise ValueError(f"contrast too low{where}: " + "; ".join(low))


async def run_design(date: str, title: str, summary: str,
                     sections: list[tuple[str, str, str]]) -> tuple[dict | None, dict]:
    """-> (theme or None, usage summed over every attempt). Never raises: a day without a theme
    still gets the base design."""
    messages = [{"role": "system", "content": prompt()},
                {"role": "user", "content": context(date, title, summary, sections)}]
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
            theme = validate(reply)
        except ValueError as e:
            log.warning("design attempt %d rejected: %s", attempt + 1, e)
            messages += [{"role": "assistant", "content": reply},
                         {"role": "user", "content": f"That stylesheet was rejected: {e}. "
                                                     "Reply with the complete corrected stylesheet only."}]
            continue
        log.info("design: %r after %d attempt(s)", theme["name"], attempt + 1)
        return theme, usage
    log.warning("design: no valid stylesheet after %d attempts; using the base design", 1 + MAX_RETRIES)
    return None, usage
