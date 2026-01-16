/**
 * API Route: /api/diary/dates
 * Returns list of dates that have diary entries
 * Used by calendar to determine which dates are clickable
 */

import { NextResponse } from "next/server";

/**
 * Mocked set of dates with available diary entries
 * In production, this would query the database for all entry dates
 */
function getAvailableDates(): string[] {
  return [
    "2026-01-01",
    "2026-01-02",
    "2026-01-03",
    "2026-01-04",
    "2026-01-05",
    "2026-01-06", // Today
  ];
}

export async function GET() {
  // Simulate network delay for realism
  await new Promise((resolve) => setTimeout(resolve, 50));

  const dates = getAvailableDates();

  return NextResponse.json({ data: dates });
}
