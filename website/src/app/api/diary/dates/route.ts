/**
 * API Route: /api/diary/dates
 * Returns list of dates that have diary entries
 * Used by the home page calendar to determine which dates are clickable
 */

import { readdir } from "node:fs/promises";
import path from "node:path";
import { NextResponse } from "next/server";

// Read on every request so a newly committed entry shows up without a rebuild
export const dynamic = "force-dynamic";

const ENTRY_FILE = /^\d{4}-\d{2}-\d{2}\.json$/;

export async function GET() {
  const files = await readdir(path.join(process.cwd(), "data")).catch(() => []);
  const dates = files
    .filter((f) => ENTRY_FILE.test(f))
    .map((f) => f.slice(0, -".json".length))
    .sort();

  return NextResponse.json({ data: dates });
}
