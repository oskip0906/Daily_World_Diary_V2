/**
 * Home page - opens the current day's report
 * Before today's entry is generated (9am New York), opens the most recent one instead
 */

import { redirect } from "next/navigation";
import { getAvailableDates, todayInNewYork } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function Home() {
  const today = todayInNewYork();
  const latest = (await getAvailableDates()).filter((d) => d <= today).at(-1);

  redirect(latest ? `/diary/${latest}` : "/calendar");
}
