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
  sources?: SourceLink[]; // Optional list of source links for the section
}

export interface DiaryEntry {
  metadata: DiaryMetadata;
  sections: DiarySection[];
}

export interface SourceLink {
  title: string;
  url: string;
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
