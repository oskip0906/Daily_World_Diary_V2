/**
 * Calendar view
 * Displays monthly calendar with clickable dates that have diary entries
 * Server component that fetches available dates on load
 */

import { CalendarGrid } from "@/components/CalendarGrid";
import { getAvailableDates } from "@/lib/api";
import { generateCalendarMonth } from "@/lib/date-utils";

export const dynamic = "force-dynamic";

export default async function CalendarPage() {
  const today = new Date();
  const currentYear = today.getFullYear();
  const currentMonth = today.getMonth();

  const datesWithEntries = new Set(await getAvailableDates());

  const initialCalendar = generateCalendarMonth(
    currentYear,
    currentMonth,
    datesWithEntries
  );

  return (
    <div className="container mx-auto px-4 py-12 lg:py-16">
      <div className="max-w-5xl mx-auto">
        {/* Page introduction */}
        <div className="mb-12 text-center">
          <h1 className="text-4xl md:text-5xl font-bold text-text-primary dark:text-dark-text-primary mb-4">
            World Diary Archive
          </h1>
          <p className="text-lg text-text-secondary dark:text-dark-text-secondary max-w-2xl mx-auto">
            Select a date to read the AI-generated daily snapshot. Each entry
            synthesizes global events across politics, markets, entertainment,
            and culture.
          </p>
        </div>

        {/* Calendar grid */}
        <CalendarGrid
          initialMonth={initialCalendar}
          datesWithEntries={datesWithEntries}
        />
      </div>
    </div>
  );
}
