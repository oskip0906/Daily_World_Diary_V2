/**
 * Where the pages fetch their own /api routes; on Vercel, defaults to the production domain
 */
export const baseUrl =
  process.env.NEXT_PUBLIC_BASE_URL ||
  (process.env.VERCEL_PROJECT_PRODUCTION_URL
    ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}`
    : "http://localhost:3000");

/**
 * Server-side fetch of the dates that have diary entries
 */
export async function getAvailableDates(): Promise<string[]> {
  try {
    const response = await fetch(`${baseUrl}/api/diary/dates`, {
      cache: "no-store", // Ensure fresh data on each page load
    });

    if (!response.ok) {
      console.error("Failed to fetch available dates");
      return [];
    }

    const { data } = await response.json();
    return data;
  } catch (error) {
    console.error("Error fetching available dates:", error);
    return [];
  }
}

/**
 * Today's date (YYYY-MM-DD) in New York, the timezone entries are dated and generated in
 */
export function todayInNewYork(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "America/New_York" }).format(new Date());
}
