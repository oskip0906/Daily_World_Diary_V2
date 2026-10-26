/**
 * API Route: /api/diary/[date]
 * Returns the diary entry generated for the requested date (website/data/YYYY-MM-DD.json)
 */

import { readFile } from "node:fs/promises";
import path from "node:path";
import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ date: string }> }
) {
  const { date } = await params;

  // The date becomes a file path, so this check is what stops path traversal
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) {
    return NextResponse.json(
      { error: "Invalid date format. Use YYYY-MM-DD" },
      { status: 400 }
    );
  }

  try {
    const file = path.join(process.cwd(), "data", `${date}.json`);
    return NextResponse.json({ data: JSON.parse(await readFile(file, "utf8")) });
  } catch {
    return NextResponse.json(
      { error: "No diary entry found for this date" },
      { status: 404 }
    );
  }
}
