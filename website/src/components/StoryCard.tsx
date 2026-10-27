/**
 * Story cards: each ### heading of a section and the text under it becomes one card.
 * The day's theme picks one of ten card components per section (CARDS in backend/diary/design.py,
 * which describes each one to the model: keep the two in step). Styles live in globals.css.
 */

import Link from "next/link";
import { CardStyle, StoryThread } from "@/types";

export const CARDS: CardStyle[] = [
  "plain", "outline", "elevated", "banner", "split",
  "numbered", "lede", "stat", "timeline", "tile",
];

export interface Story {
  title: string | null; // HTML inside the <h3>; null for text before a section's first heading
  body: string;
}

const LEDE = /^\s*<p>([\s\S]*?)<\/p>\s*([\s\S]*)$/;
// a percentage, basis points, a dollar amount, or a number with a scale word; never a bare year
const FIGURE =
  /[+\-−]?\$?\d[\d,]*(?:\.\d+)?\s?(?:%|percent\b|bps\b|(?:trillion|billion|million)\b)|[+\-−]?\$\d[\d,]*(?:\.\d+)?/i;

// a citation of a Spotify album or track (backend/diary/sources/spotify.py): becomes a player
const SPOTIFY_LINK =
  /\s*<a href="https:\/\/open\.spotify\.com\/(album|track)\/([A-Za-z0-9]{22})(?:\?[^"]*)?"[^>]*>[^<]*<\/a>([.,;:]?)/g;

/**
 * Spotify citations -> embedded players. The iframe src is rebuilt from the two captured parts,
 * which the regex limits to a type keyword and a 22-character base62 id, so nothing else reaches it.
 */
export function embedSpotify(html: string): string {
  return html.replace(
    SPOTIFY_LINK,
    // the sentence's own punctuation stays with the sentence, before the player
    (_, type: string, id: string, punctuation: string) =>
      `${punctuation}<iframe class="diary-embed" src="https://open.spotify.com/embed/${type}/${id}" height="152" ` +
      `loading="lazy" allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" ` +
      `title="Play on Spotify"></iframe>`
  );
}

/** Whether section HTML has a Spotify citation, which embedSpotify turns into a player */
export function hasPlayers(html: string): boolean {
  return html.search(SPOTIFY_LINK) !== -1; // search ignores the g flag's lastIndex
}

/**
 * Section HTML (sanitized by backend/diary/render.py, whose headings are bare <h3>) -> stories
 */
export function splitStories(html: string): Story[] {
  return html
    .split(/(?=<h3>)/)
    .map((chunk) => chunk.trim())
    .filter(Boolean)
    .map((chunk) => {
      const m = chunk.match(/^<h3>([\s\S]*?)<\/h3>\s*([\s\S]*)$/);
      return m ? { title: m[1], body: m[2] } : { title: null, body: chunk };
    });
}

interface StoryCardProps {
  story: Story;
  card: CardStyle;
  index: number;
  thread?: StoryThread;
}

export function StoryCard({ story, card, index, thread }: StoryCardProps) {
  const lede = card === "lede" ? story.body.match(LEDE) : null;
  const body = embedSpotify(lede ? lede[2] : story.body);
  const figure = card === "stat" ? story.body.replace(/<[^>]+>/g, " ").match(FIGURE)?.[0].trim() : undefined;

  return (
    <article className={`diary-card diary-card--${card}`}>
      <div className="diary-card-inner">
        {card === "numbered" && <span className="diary-card-index">{String(index).padStart(2, "0")}</span>}
        {figure && <p className="diary-card-figure">{figure}</p>}
        {story.title && <h3 className="diary-card-title" dangerouslySetInnerHTML={{ __html: story.title }} />}
        {thread && (
          <Link className="diary-card-thread" href={`/threads/${thread.id}`}>
            Day {thread.day} · {thread.title}
          </Link>
        )}
        {lede && <p className="diary-card-lede" dangerouslySetInnerHTML={{ __html: lede[1] }} />}
        {body.trim() && <div className="diary-card-body diary-prose" dangerouslySetInnerHTML={{ __html: body }} />}
      </div>
    </article>
  );
}
