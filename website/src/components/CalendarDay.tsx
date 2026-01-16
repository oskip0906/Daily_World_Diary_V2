/**
 * Calendar day cell component
 * Renders individual day with appropriate styling and interactivity
 */

import Link from "next/link";
import { CalendarDay as CalendarDayType } from "@/types";
import { isToday } from "@/lib/date-utils";

interface CalendarDayProps {
  day: CalendarDayType;
}

export function CalendarDay({ day }: CalendarDayProps) {
  const { date, dayOfMonth, hasEntry, isCurrentMonth } = day;
  const today = isToday(date);

  // Non-current month days are muted and non-interactive
  if (!isCurrentMonth) {
    return (
      <div className="aspect-square p-2 flex items-start justify-center">
        <span className="text-sm text-text-muted dark:text-dark-text-muted opacity-40">
          {dayOfMonth}
        </span>
      </div>
    );
  }

  // Days without entries are displayed but not clickable
  if (!hasEntry) {
    return (
      <div
        className={`aspect-square p-2 flex items-start justify-center border border-transparent ${
          today
            ? "bg-bg-tertiary dark:bg-dark-bg-tertiary"
            : "bg-bg-secondary dark:bg-dark-bg-secondary"
        }`}
      >
        <span
          className={`text-sm ${
            today
              ? "font-semibold text-text-primary dark:text-dark-text-primary"
              : "text-text-muted dark:text-dark-text-muted"
          }`}
        >
          {dayOfMonth}
        </span>
      </div>
    );
  }

  // Days with entries are interactive links
  return (
    <Link
      href={`/diary/${date}`}
      className={`aspect-square p-2 flex items-start justify-center border transition-all ${
        today
          ? "border-accent dark:border-dark-accent bg-accent/5 dark:bg-dark-accent/5"
          : "border-border dark:border-dark-border hover:border-accent dark:hover:border-dark-accent"
      } hover:bg-accent/10 dark:hover:bg-dark-accent/10`}
    >
      <span
        className={`text-sm font-medium ${
          today
            ? "text-accent dark:text-dark-accent"
            : "text-text-primary dark:text-dark-text-primary"
        }`}
      >
        {dayOfMonth}
      </span>
    </Link>
  );
}
