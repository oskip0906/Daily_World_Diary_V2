/**
 * Home page: the latest edition, with a cover in that day's own palette and headline font, and a
 * calendar of every edition. Styled by the reader's chosen theme.
 */

import type { CSSProperties } from "react";
import Link from "next/link";
import { cookies } from "next/headers";
import { CalendarGrid } from "@/components/CalendarGrid";
import { ThemePicker } from "@/components/ThemePicker";
import { getAvailableDates, getDiaryEntry, todayInNewYork } from "@/lib/api";
import { parseDate } from "@/lib/date-utils";
import { THEME_COOKIE, readTheme } from "@/lib/themes";
import { DiaryEntry } from "@/types";

export const dynamic = "force-dynamic";

/**
 * A day's colours and headline font, read from its validated theme CSS (backend/diary/design.py),
 * so the cover looks like the edition it opens
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

export default async function Home() {
  const theme = readTheme((await cookies()).get(THEME_COOKIE)?.value);
  const today = todayInNewYork();
  const dates = await getAvailableDates();
  // before 9am New York, today's entry doesn't exist yet: lead with the latest one
  const latestDate = dates.filter((d) => d <= today).at(-1);
  const latest = latestDate ? await getDiaryEntry(latestDate) : null;
  const shown = parseDate(latestDate ?? today);

  return (
    <div className="diary-page home" data-theme={theme}>
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
        {latestDate && latest ? (
          <section className="home-lead" aria-labelledby="home-lead-title">
            <div className="home-lead-text">
              <p className="home-kicker">
                {latestDate === today ? "Today's edition" : "Latest edition"} · {longDate(latestDate, { weekday: "long" })}
              </p>
              <h2 id="home-lead-title" className="home-lead-title">{latest.metadata.title}</h2>
              {latest.metadata.summary && <p className="home-lead-summary">{latest.metadata.summary}</p>}
              <Link className="home-button" href={`/diary/${latestDate}`}>Read the edition →</Link>
            </div>
            <Link href={`/diary/${latestDate}`} className="home-cover" style={palette(latest)}>
              <span className="home-cover-date">{longDate(latestDate, { weekday: "short", month: "short", day: "numeric" })}</span>
              <span className="home-cover-name">{latest.theme?.name ?? latest.metadata.title}</span>
              {latest.theme && <span className="home-cover-note">{latest.theme.note}</span>}
              <span className="home-cover-swatches" aria-hidden="true">
                <i /> <i /> <i /> <i />
              </span>
            </Link>
          </section>
        ) : (
          <p className="home-empty">The first edition is on its way.</p>
        )}

        <section className="home-block" aria-labelledby="home-archive">
          <h2 id="home-archive" className="home-heading">Every edition</h2>
          <CalendarGrid year={shown.getFullYear()} month={shown.getMonth()} today={today} dates={dates} />
        </section>
      </main>
    </div>
  );
}
