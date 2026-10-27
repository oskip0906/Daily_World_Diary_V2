/**
 * Date utility functions for calendar navigation and formatting
 * All dates use ISO 8601 format (YYYY-MM-DD) for consistency
 */

import { CalendarDay, CalendarMonth } from "@/types";

/**
 * Format date to YYYY-MM-DD
 */
export function formatDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

/**
 * Parse YYYY-MM-DD string to Date object
 */
export function parseDate(dateString: string): Date {
  const [year, month, day] = dateString.split("-").map(Number);
  return new Date(year, month - 1, day);
}

/**
 * Get month name from 0-indexed month number
 */
export function getMonthName(month: number): string {
  const months = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
  ];
  return months[month];
}

/**
 * Generate calendar grid for a given month
 * Includes padding days from previous/next months for complete weeks
 */
export function generateCalendarMonth(
  year: number,
  month: number,
  datesWithEntries: Set<string>
): CalendarMonth {
  const firstDay = new Date(year, month, 1);
  const lastDay = new Date(year, month + 1, 0);

  const days: CalendarDay[] = [];

  // Add padding days from previous month
  const firstDayOfWeek = firstDay.getDay(); // 0 = Sunday
  const prevMonthLastDay = new Date(year, month, 0);
  for (let i = firstDayOfWeek - 1; i >= 0; i--) {
    const date = new Date(year, month - 1, prevMonthLastDay.getDate() - i);
    days.push({
      date: formatDate(date),
      dayOfMonth: date.getDate(),
      hasEntry: false,
      isCurrentMonth: false,
    });
  }

  // Add days of current month
  for (let day = 1; day <= lastDay.getDate(); day++) {
    const date = new Date(year, month, day);
    const dateString = formatDate(date);
    days.push({
      date: dateString,
      dayOfMonth: day,
      hasEntry: datesWithEntries.has(dateString),
      isCurrentMonth: true,
    });
  }

  // Add padding days from next month
  const lastDayOfWeek = lastDay.getDay(); // 0 = Sunday
  const remainingDays = 6 - lastDayOfWeek;
  for (let i = 1; i <= remainingDays; i++) {
    const date = new Date(year, month + 1, i);
    days.push({
      date: formatDate(date),
      dayOfMonth: date.getDate(),
      hasEntry: false,
      isCurrentMonth: false,
    });
  }

  return { year, month, days };
}

/**
 * Navigate to previous month
 */
export function getPreviousMonth(year: number, month: number) {
  if (month === 0) {
    return { year: year - 1, month: 11 };
  }
  return { year, month: month - 1 };
}

/**
 * Navigate to next month
 */
export function getNextMonth(year: number, month: number) {
  if (month === 11) {
    return { year: year + 1, month: 0 };
  }
  return { year, month: month + 1 };
}

/**
 * Format date for display (e.g., "January 15, 2024")
 */
export function formatDateLong(dateString: string): string {
  const date = parseDate(dateString);
  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}
