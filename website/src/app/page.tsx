/**
 * Home page: today's edition, the markets, the stories being followed, and the recent editions,
 * each drawn as a cover in its own day's palette. Styled by the reader's chosen theme.
 */

import type { CSSProperties } from "react";
import Link from "next/link";
import { cookies } from "next/headers";
import { MarketCharts } from "@/components/MarketCharts";
import { ThemePicker } from "@/components/ThemePicker";
import { getAvailableDates, getDiaryEntry, todayInNewYork } from "@/lib/api";
import { parseDate } from "@/lib/date-utils";
import { THEME_COOKIE, readTheme } from "@/lib/themes";
import { DiaryEntry } from "@/types";

export const dynamic = "force-dynamic";

const RECENT = 6;

/**
 * A day's colours and headline font, read from its validated theme CSS (backend/diary/design.py),
 * so a cover looks like the edition it opens
 * shortcut: reads the first plain `.diary-page {` block, which the design prompt asks to come first
 */
function palette(entry: DiaryEntry): CSSProperties {
  const root = entry.theme?.css.match(/\.diary-page\s*\{([^}]*)\}/)?.[1] ?? "";
  const hex = (token: string) => root.match(new RegExp(`${token}\\s*:\\s*(#[0-9a-fA-F]{6})\\b`))?.[1];
  const font = root.match(/--font-display\s*:\s*var\((--ff-[\w-]+)\)/)?.[1];
  const vars: Record<string, string> = {};
  for (const [name, token] of [["--cover-paper", "--paper"], ["--cover-alt", "--paper-alt"],
                               ["--cover-ink", "--ink"], ["--cover-accent", "--accent"]]) {
    const value = hex(token);
    if (value) vars[name] = value;
  }
  if (font) vars["--cover-font"] = `var(${font})`;
  return vars as CSSProperties;
}

const longDate = (date: string, options: Intl.DateTimeFormatOptions) =>
  parseDate(date).toLocaleDateString("en-US", options);

function Cover({ date, entry, featured = false }: { date: string; entry: DiaryEntry; featured?: boolean }) {
  return (
    <Link href={`/diary/${date}`} className={`home-cover${featured ? " home-cover--featured" : ""}`} style={palette(entry)}>
      <span className="home-cover-date">{longDate(date, { weekday: "short", month: "short", day: "numeric" })}</span>
      <span className="home-cover-name">{entry.theme?.name ?? entry.metadata.title}</span>
      {featured && entry.theme && <span className="home-cover-note">{entry.theme.note}</span>}
      <span className="home-cover-swatches" aria-hidden="true">
        <i /> <i /> <i /> <i />
      </span>
    </Link>
  );
}

export default async function Home() {
  const theme = readTheme((await cookies()).get(THEME_COOKIE)?.value);
  const today = todayInNewYork();
  // before 9am New York, today's entry doesn't exist yet: lead with the latest one
  const dates = (await getAvailableDates()).filter((d) => d <= today).reverse().slice(0, RECENT);
  const entries = (await Promise.all(dates.map(async (d) => [d, await getDiaryEntry(d)] as const)))
    .filter((pair): pair is readonly [string, DiaryEntry] => pair[1] !== null);
  const [latest, ...recent] = entries;

  const indices = latest?.[1].sections.flatMap((s) => s.charts ?? []).filter((c) => c.group === "Indices") ?? [];
  const following = [
    ...new Map(entries.flatMap(([d, e]) => (e.threads ?? []).map((t) => [t.id, { ...t, date: d }] as const)).reverse())
      .values(),
  ].sort((a, b) => b.date.localeCompare(a.date) || b.day - a.day);

  return (
    <div className="diary-page home" data-theme={theme === "auto" ? undefined : theme}>
      <header className="home-masthead">
        <div className="home-inner">
          <div className="home-topbar">
            <span className="home-today-date">{longDate(today, { weekday: "long", month: "long", day: "numeric", year: "numeric" })}</span>
            <ThemePicker current={theme} />
          </div>
          <h1 className="home-wordmark">Daily World Diary</h1>
          <p className="home-tagline">The world, written and designed fresh every morning by AI.</p>
        </div>
      </header>

      <main className="home-inner home-main">
        {latest ? (
          <section className="home-lead" aria-labelledby="home-lead-title">
            <div className="home-lead-text">
              <p className="home-kicker">{latest[0] === today ? "Today's edition" : "Latest edition"} · {longDate(latest[0], { weekday: "long" })}</p>
              <h2 id="home-lead-title" className="home-lead-title">{latest[1].metadata.title}</h2>
              {latest[1].metadata.summary && <p className="home-lead-summary">{latest[1].metadata.summary}</p>}
              <div className="home-lead-actions">
                <Link className="home-button" href={`/diary/${latest[0]}`}>Read the edition →</Link>
                <span className="home-lead-meta">
                  {latest[1].sections.length} sections
                  {latest[1].threads?.length ? ` · ${latest[1].threads.length} developing ${latest[1].threads.length === 1 ? "story" : "stories"}` : ""}
                </span>
              </div>
            </div>
            <Cover date={latest[0]} entry={latest[1]} featured />
          </section>
        ) : (
          <p className="home-empty">The first edition is on its way.</p>
        )}

        {indices.length > 0 && (
          <section className="home-block" aria-labelledby="home-markets">
            <h2 id="home-markets" className="home-heading">Markets</h2>
            <MarketCharts charts={indices} />
          </section>
        )}

        {following.length > 0 && (
          <section className="home-block" aria-labelledby="home-following">
            <h2 id="home-following" className="home-heading">Following</h2>
            <ul className="home-threads">
              {following.map((t) => (
                <li key={t.id}>
                  <Link className="home-thread" href={`/threads/${t.id}`}>
                    <span className="home-thread-day">Day {t.day}</span>
                    <span className="home-thread-title">{t.title}</span>
                    <span className="home-thread-date">{longDate(t.date, { month: "short", day: "numeric" })}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        )}

        {recent.length > 0 && (
          <section className="home-block" aria-labelledby="home-recent">
            <h2 id="home-recent" className="home-heading">Recent editions</h2>
            <p className="home-subheading">Every day is designed from its own news.</p>
            <div className="home-covers">
              {recent.map(([d, e]) => (
                <Cover key={d} date={d} entry={e} />
              ))}
            </div>
          </section>
        )}

        <footer className="home-footer">
          <Link href="/calendar">Browse the full archive →</Link>
        </footer>
      </main>
    </div>
  );
}
