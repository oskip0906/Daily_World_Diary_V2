/**
 * API Route: /api/threads/[id]
 * Returns one story thread with every story in it, oldest first.
 * Entries are write-once, so the latest entry in the thread lists all of its earlier stories
 * (StoryThread.follows); each ref is resolved to that day's card.
 */

import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import { NextRequest, NextResponse } from "next/server";
import { splitStories } from "@/components/StoryCard";
import { DiaryEntry } from "@/types";

export const dynamic = "force-dynamic";

const ENTRY_FILE = /^\d{4}-\d{2}-\d{2}\.json$/;
const SLUG = /^[a-z0-9]+(?:-[a-z0-9]+){0,7}$/; // as backend/diary/threads.py
const REF = /^(\d{4}-\d{2}-\d{2})\/([a-z0-9-]+)\/(\d+)$/;

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  if (!SLUG.test(id)) {
    return NextResponse.json({ error: "Invalid thread id" }, { status: 400 });
  }

  const dir = path.join(process.cwd(), "data");
  const files = (await readdir(dir).catch(() => [])).filter((f) => ENTRY_FILE.test(f)).sort();
  // filenames come from readdir and match ENTRY_FILE, so nothing here reaches a path unchecked
  const entries = new Map<string, DiaryEntry>();
  for (const f of files) {
    entries.set(f.slice(0, -".json".length), JSON.parse(await readFile(path.join(dir, f), "utf8")));
  }

  const latest = [...entries].reverse().find(([, e]) => e.threads?.some((t) => t.id === id));
  if (!latest) {
    return NextResponse.json({ error: "No such thread" }, { status: 404 });
  }
  const [date, entry] = latest;
  const thread = entry.threads!.filter((t) => t.id === id);
  const refs = [...new Set([...thread.flatMap((t) => t.follows), ...thread.map((t) => `${date}/${t.story}`)])].sort();

  const stories = refs.flatMap((ref) => {
    const m = ref.match(REF);
    const section = m && entries.get(m[1])?.sections.find((s) => s.id === m[2]);
    const story = section && splitStories(section.content)[Number(m[3]) - 1];
    return story ? [{ ref, date: m[1], sectionId: section.id, sectionTitle: section.title, ...story }] : [];
  });

  return NextResponse.json({
    data: { id, title: thread[thread.length - 1].title, day: Math.max(...thread.map((t) => t.day)), stories },
  });
}
