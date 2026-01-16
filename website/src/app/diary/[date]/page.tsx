/**
 * Dynamic diary entry page
 * Displays full diary entry with sections, TOC, and prompt transparency
 * Server component that fetches diary data and prompts on load
 */

import { notFound } from "next/navigation";
import Link from "next/link";
import { DiaryLayout } from "@/components/DiaryLayout";
import { DiarySection } from "@/components/DiarySection";
import { PromptViewer } from "@/components/PromptViewer";
import { formatDateLong } from "@/lib/date-utils";
import { DiaryEntry, PromptsResponse, TocItem } from "@/types";

interface DiaryPageProps {
  params: Promise<{ date: string }>;
}

/**
 * Fetch diary entry from API
 */
async function getDiaryEntry(date: string): Promise<DiaryEntry | null> {
  try {
    const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || "http://localhost:3000";
    const response = await fetch(`${baseUrl}/api/diary/${date}`, {
      cache: "no-store",
    });

    if (!response.ok) {
      return null;
    }

    const { data } = await response.json();
    return data;
  } catch (error) {
    console.error("Error fetching diary entry:", error);
    return null;
  }
}

/**
 * Fetch agent prompts from API
 */
async function getPrompts(): Promise<PromptsResponse | null> {
  try {
    const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || "http://localhost:3000";
    const response = await fetch(`${baseUrl}/api/prompts`, {
      cache: "force-cache", // Prompts change infrequently
    });

    if (!response.ok) {
      return null;
    }

    return await response.json();
  } catch (error) {
    console.error("Error fetching prompts:", error);
    return null;
  }
}

export default async function DiaryPage({ params }: DiaryPageProps) {
  const { date } = await params;

  // Fetch diary entry and prompts in parallel
  const [diaryEntry, promptsResponse] = await Promise.all([
    getDiaryEntry(date),
    getPrompts(),
  ]);

  // Handle missing entry
  if (!diaryEntry) {
    notFound();
  }

  // Build table of contents from sections
  const tocItems: TocItem[] = diaryEntry.sections.map((section) => ({
    id: section.id,
    title: section.title,
    order: section.order,
  }));

  // Add prompts section to TOC if available
  if (promptsResponse) {
    tocItems.push({
      id: "prompts",
      title: "Prompt Transparency",
      order: 999,
    });
  }

  return (
    <>
      {/* Page header with metadata */}
      <div className="border-b border-border dark:border-dark-border bg-bg-secondary dark:bg-dark-bg-secondary">
        <div className="container mx-auto px-4 py-8">
          <div className="max-w-3xl">
            <Link
              href="/"
              className="inline-flex items-center text-sm text-accent dark:text-dark-accent hover:text-accent-hover dark:hover:text-dark-accent-hover mb-4"
            >
              ← Back to Calendar
            </Link>
            <h1 className="text-3xl md:text-4xl lg:text-5xl font-bold text-text-primary dark:text-dark-text-primary mb-3">
              {diaryEntry.metadata.title}
            </h1>
            <div className="flex flex-wrap items-center gap-4 text-sm text-text-muted dark:text-dark-text-muted">
              <time dateTime={diaryEntry.metadata.date}>
                {formatDateLong(diaryEntry.metadata.date)}
              </time>
              <span>•</span>
              <span>
                Generated{" "}
                {new Date(diaryEntry.metadata.generatedAt).toLocaleString()}
              </span>
            </div>
            <p className="mt-4 text-lg text-text-secondary dark:text-dark-text-secondary">
              {diaryEntry.metadata.summary}
            </p>
          </div>
        </div>
      </div>

      {/* Main content with TOC sidebar */}
      <DiaryLayout tocItems={tocItems}>
        {/* Render diary sections */}
        {diaryEntry.sections
          .sort((a, b) => a.order - b.order)
          .map((section) => (
            <DiarySection key={section.id} section={section} />
          ))}

        {/* Prompt transparency section */}
        {promptsResponse && (
          <PromptViewer prompts={promptsResponse.prompts} />
        )}
      </DiaryLayout>
    </>
  );
}

/**
 * Generate metadata for SEO
 */
export async function generateMetadata({
  params,
}: DiaryPageProps) {
  const { date } = await params;
  const diaryEntry = await getDiaryEntry(date);

  if (!diaryEntry) {
    return {
      title: "Entry Not Found",
    };
  }

  return {
    title: `${diaryEntry.metadata.title} | Daily World Diary`,
    description: diaryEntry.metadata.summary,
  };
}
