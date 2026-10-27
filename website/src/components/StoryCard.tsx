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
  const body = lede ? lede[2] : story.body;
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
