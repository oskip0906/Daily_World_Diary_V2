/**
 * Core domain types for Daily World Diary
 * These interfaces define the shape of diary entries, sections, and metadata
 */

export interface DiaryMetadata {
  date: string; // ISO 8601 format (YYYY-MM-DD)
  title: string;
  summary: string;
  generatedAt: string; // ISO 8601 timestamp
}

export interface DiarySection {
  id: string; // Used for anchor navigation in TOC
  title: string;
  content: string; // MDX/Markdown content
  order: number; // Display order
  charts?: MarketChart[]; // stock-analysis only: the last week's closes per index and sector
}

export interface MarketChart {
  group: string; // "Indices" | "Sectors"
  label: string;
  symbol: string;
  change: number; // % change in the last session
  closes: number[]; // oldest first
}

/**
 * A story that continues earlier ones (backend/diary/threads.py)
 */
export interface StoryThread {
  id: string;
  title: string;
  story: string; // "<section id>/<n>": card n (from 1) of that section
  day: number; // how many days the thread has run, today included
  follows: string[]; // every earlier story of the thread: "YYYY-MM-DD/<section id>/<n>"
}

/**
 * The day's design, written by the backend's design step (backend/diary/design.py)
 */
export type HeroStyle = "classic" | "centered" | "split" | "poster";
export type CardStyle =
  | "plain" | "outline" | "elevated" | "banner" | "split"
  | "numbered" | "lede" | "stat" | "timeline" | "tile";
export type StoryLayout = "stack" | "grid-2" | "grid-3" | "feature" | "masonry" | "rail";

export interface DiaryTheme {
  name: string;
  note: string; // one sentence on how the design reflects the day
  mood?: "good" | "bad" | "tragic" | "tense" | "neutral"; // sets the palette; absent on themes before 2026-10-27
  hero?: HeroStyle; // absent on themes from before the card components existed
  sections?: Record<string, { card: CardStyle; layout: StoryLayout }>;
  css: string; // validated there: every selector scoped to .diary-page, no external resources
}

export interface DiaryEntry {
  metadata: DiaryMetadata;
  sections: DiarySection[];
  theme?: DiaryTheme; // absent on entries before 2026-10-26 or when the design step gave up
  threads?: StoryThread[];
}

/**
 * Calendar-related types
 */
export interface CalendarDay {
  date: string; // ISO 8601 format (YYYY-MM-DD)
  dayOfMonth: number;
  hasEntry: boolean;
  isCurrentMonth: boolean;
}

export interface CalendarMonth {
  year: number;
  month: number; // 0-indexed (0 = January, 11 = December)
  days: CalendarDay[];
}

/**
 * Table of Contents types for navigation
 */
export interface TocItem {
  id: string;
  title: string;
  order: number;
}

/**
 * Utility type for API responses
 */
export interface ApiResponse<T> {
  data: T;
  error?: string;
}
