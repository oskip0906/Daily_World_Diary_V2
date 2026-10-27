/**
 * Calendar day cell: a link when the day has an entry, plain text otherwise
 */

import Link from "next/link";
import { CalendarDay as CalendarDayType } from "@/types";

interface CalendarDayProps {
  day: CalendarDayType;
  today: boolean;
}

export function CalendarDay({ day, today }: CalendarDayProps) {
  const { date, dayOfMonth, hasEntry, isCurrentMonth } = day;
  const className = `home-cal-day${isCurrentMonth ? "" : " is-outside"}${today ? " is-today" : ""}`;

  return hasEntry ? (
    <Link href={`/diary/${date}`} className={`${className} has-entry`} aria-label={`Read the edition for ${date}`}>
      {dayOfMonth}
    </Link>
  ) : (
    <span className={className}>{dayOfMonth}</span>
  );
}
