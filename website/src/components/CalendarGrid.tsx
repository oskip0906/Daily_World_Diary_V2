"use client";

/**
 * Calendar grid component with month navigation
 * Displays a monthly calendar view with clickable days that have diary entries
 */

import { useState } from "react";
import { CalendarMonth } from "@/types";
import { CalendarDay } from "./CalendarDay";
import {
  getMonthName,
  getPreviousMonth,
  getNextMonth,
  generateCalendarMonth,
} from "@/lib/date-utils";

interface CalendarGridProps {
  initialMonth: CalendarMonth;
  datesWithEntries: Set<string>;
}

const WEEKDAY_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

export function CalendarGrid({
  initialMonth,
  datesWithEntries,
}: CalendarGridProps) {
  const [currentYear, setCurrentYear] = useState(initialMonth.year);
  const [currentMonth, setCurrentMonth] = useState(initialMonth.month);

  const calendar = generateCalendarMonth(
    currentYear,
    currentMonth,
    datesWithEntries
  );

  const handlePreviousMonth = () => {
    const { year, month } = getPreviousMonth(currentYear, currentMonth);
    setCurrentYear(year);
    setCurrentMonth(month);
  };

  const handleNextMonth = () => {
    const { year, month } = getNextMonth(currentYear, currentMonth);
    setCurrentYear(year);
    setCurrentMonth(month);
  };

  return (
    <div className="w-full max-w-4xl mx-auto">
      {/* Month navigation header */}
      <div className="flex items-center justify-between mb-6">
        <button
          onClick={handlePreviousMonth}
          className="px-4 py-2 text-sm font-medium text-text-secondary dark:text-dark-text-secondary hover:text-accent dark:hover:text-dark-accent transition-colors"
          aria-label="Previous month"
        >
          ← Previous
        </button>

        <h2 className="text-2xl md:text-3xl font-semibold text-text-primary dark:text-dark-text-primary">
          {getMonthName(currentMonth)} {currentYear}
        </h2>

        <button
          onClick={handleNextMonth}
          className="px-4 py-2 text-sm font-medium text-text-secondary dark:text-dark-text-secondary hover:text-accent dark:hover:text-dark-accent transition-colors"
          aria-label="Next month"
        >
          Next →
        </button>
      </div>

      {/* Weekday labels */}
      <div className="grid grid-cols-7 gap-1 mb-1">
        {WEEKDAY_LABELS.map((label) => (
          <div
            key={label}
            className="p-2 text-center text-xs font-semibold text-text-muted dark:text-dark-text-muted uppercase tracking-wider"
          >
            {label}
          </div>
        ))}
      </div>

      {/* Calendar grid */}
      <div className="grid grid-cols-7 gap-1">
        {calendar.days.map((day, index) => (
          <CalendarDay key={`${day.date}-${index}`} day={day} />
        ))}
      </div>

      {/* Legend */}
      <div className="mt-6 flex flex-wrap gap-4 text-sm text-text-muted dark:text-dark-text-muted">
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 border border-border dark:border-dark-border" />
          <span>Entry available</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 bg-bg-secondary dark:bg-dark-bg-secondary" />
          <span>No entry</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 border border-accent dark:border-dark-accent bg-accent/5 dark:bg-dark-accent/5" />
          <span>Today</span>
        </div>
      </div>
    </div>
  );
}
