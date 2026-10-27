"use client";

/**
 * Calendar grid component with month navigation, on the home page
 * Days with an entry link to it; styled by the home page theme (globals.css, .home-cal)
 */

import { useState } from "react";
import { CalendarDay } from "./CalendarDay";
import { getMonthName, getPreviousMonth, getNextMonth, generateCalendarMonth } from "@/lib/date-utils";

interface CalendarGridProps {
  year: number;
  month: number; // 0-indexed
  today: string; // YYYY-MM-DD in New York, from the server, so both renders agree
  dates: string[];
}

const WEEKDAY_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

export function CalendarGrid({ year, month, today, dates }: CalendarGridProps) {
  const [current, setCurrent] = useState({ year, month });
  const calendar = generateCalendarMonth(current.year, current.month, new Set(dates));

  return (
    <div className="home-cal">
      <div className="home-cal-head">
        <button
          type="button"
          className="home-cal-nav"
          onClick={() => setCurrent(getPreviousMonth(current.year, current.month))}
          aria-label="Previous month"
        >
          ←
        </button>
        <h3 className="home-cal-month" aria-live="polite">
          {getMonthName(current.month)} {current.year}
        </h3>
        <button
          type="button"
          className="home-cal-nav"
          onClick={() => setCurrent(getNextMonth(current.year, current.month))}
          aria-label="Next month"
        >
          →
        </button>
      </div>

      <div className="home-cal-grid">
        {WEEKDAY_LABELS.map((label) => (
          <div key={label} className="home-cal-weekday">
            {label}
          </div>
        ))}
        {calendar.days.map((day, index) => (
          <CalendarDay key={`${day.date}-${index}`} day={day} today={day.date === today} />
        ))}
      </div>
    </div>
  );
}
