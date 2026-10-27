/**
 * Dynamic diary entry page
 * Displays full diary entry with sections and TOC, styled by the day's generated theme
 * Server component that fetches diary data on load
 *
 * The markup below is what the backend's design step styles: keep PAGE in
 * backend/diary/design.py in step with it.
 */

import { cookies } from "next/headers";
import { notFound } from "next/navigation";
import Link from "next/link";
import { DiarySection, LAYOUTS } from "@/components/DiarySection";
import { CARDS } from "@/components/StoryCard";
import { TableOfContents } from "@/components/TableOfContents";
import { formatDateLong, parseDate } from "@/lib/date-utils";
import { baseUrl, getAvailableDates } from "@/lib/api";
import { THEME_COOKIE, readTheme } from "@/lib/themes";
import { DiaryEntry, HeroStyle, TocItem } from "@/types";

const HEROES: HeroStyle[] = ["classic", "centered", "split", "poster"];

interface DiaryPageProps {
  params: Promise<{ date: string }>;
}

/**
 * Fetch diary entry from API
 */
async function getDiaryEntry(date: string): Promise<DiaryEntry | null> {
  try {
    const response = await fetch(`${baseUrl}/api/diary/${date}`, {
      cache: "no-store",
    });

    if (!response.ok) {
      return null;
    }

    const { data } = await response.json();
    return data;
  } catch (error) {
    console.error("Error fetching diary entry:", error);
    return null;
  }
}

function monthDay(date: string): string {
  return parseDate(date).toLocaleDateString("en-US", { month: "long", day: "numeric" });
}

export default async function DiaryPage({ params }: DiaryPageProps) {
  const { date } = await params;

  const [diaryEntry, dates] = await Promise.all([getDiaryEntry(date), getAvailableDates()]);

  // Handle missing entry
  if (!diaryEntry) {
    notFound();
  }

  const sections = [...diaryEntry.sections].sort((a, b) => a.order - b.order);
  const tocItems: TocItem[] = sections.map((section) => ({
    id: section.id,
    title: section.title,
    order: section.order,
  }));

  const index = dates.indexOf(date);
  const prev = index > 0 ? dates[index - 1] : null;
  const next = index >= 0 && index < dates.length - 1 ? dates[index + 1] : null;
  const weekday = parseDate(date).toLocaleDateString("en-US", { weekday: "long" });
  const generated = new Date(diaryEntry.metadata.generatedAt).toLocaleString("en-US", {
    timeZone: "America/New_York",
    dateStyle: "medium",
    timeStyle: "short",
  });
  // the backend already rejects "<"; checked again because this is injected raw
  const theme = diaryEntry.theme && !diaryEntry.theme.css.includes("<") ? diaryEntry.theme : null;
  // a reader theme replaces the day's CSS; its structural picks (header, cards, layouts) stay
  const daily = readTheme((await cookies()).get(THEME_COOKIE)?.value) === "daily";
  // the picks are data: anything unknown falls back to the base design's choice
  const hero = theme?.hero && HEROES.includes(theme.hero) ? theme.hero : "classic";
  const picks = (id: string) => {
    const pick = theme?.sections?.[id];
    return {
      card: pick && CARDS.includes(pick.card) ? pick.card : "plain",
      layout: pick && LAYOUTS.includes(pick.layout) ? pick.layout : "stack",
    };
  };

  return (
    <div className="diary-page" id="top" data-date={date} data-hero={hero}>
      {theme && daily && <style dangerouslySetInnerHTML={{ __html: theme.css }} />}

      <header className="diary-hero">
        <div className="diary-hero-inner">
          <nav className="diary-crumbs">
            <Link href="/calendar">All entries</Link>
          </nav>
          <p className="diary-kicker">
            <time dateTime={date}>{weekday} edition</time>
          </p>
          <h1 className="diary-title">{diaryEntry.metadata.title}</h1>
          {diaryEntry.metadata.summary && <p className="diary-summary">{diaryEntry.metadata.summary}</p>}
          {theme && daily && (
            <p className="diary-theme-note">
              <span className="diary-theme-name">{theme.name}</span> {theme.note}
            </p>
          )}
        </div>
      </header>

      <div className="diary-body">
        <TableOfContents items={tocItems} />
        <article className="diary-article">
          {sections.map((section, i) => (
            <DiarySection
              key={section.id}
              section={section}
              number={i + 1}
              threads={diaryEntry.threads ?? []}
              {...picks(section.id)}
            />
          ))}
        </article>
      </div>

      <footer className="diary-footer">
        {prev ? (
          <Link className="diary-footer-prev" href={`/diary/${prev}`}>
            ← {monthDay(prev)}
          </Link>
        ) : (
          <span />
        )}
        <span className="diary-footer-meta">Generated {generated} ET</span>
        {next ? (
          <Link className="diary-footer-next" href={`/diary/${next}`}>
            {monthDay(next)} →
          </Link>
        ) : (
          <span />
        )}
      </footer>
    </div>
  );
}

/**
 * Generate metadata for SEO
 */
export async function generateMetadata({
  params,
}: DiaryPageProps) {
  const { date } = await params;
  const diaryEntry = await getDiaryEntry(date);

  if (!diaryEntry) {
    return {
      title: "Entry Not Found",
    };
  }

  return {
    title: `${diaryEntry.metadata.title} | Daily World Diary`,
    description: diaryEntry.metadata.summary || formatDateLong(date),
  };
}
