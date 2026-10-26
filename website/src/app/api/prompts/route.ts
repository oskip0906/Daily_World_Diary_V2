/**
 * API Route: /api/prompts
 * Returns system prompts for all AI agents.
 * website/data/prompts.json is written by the backend from its agent registry (backend/diary/prompts.py)
 * on every generation run, so the prompts shown are the prompts the agents actually ran.
 */

import { readFile } from "node:fs/promises";
import path from "node:path";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const file = path.join(process.cwd(), "data", "prompts.json");
    return NextResponse.json(JSON.parse(await readFile(file, "utf8")));
  } catch {
    return NextResponse.json({ error: "Prompts not generated yet" }, { status: 404 });
  }
}
