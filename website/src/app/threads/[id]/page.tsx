/**
 * Story thread page: one developing story, day by day, on the base diary design
 */

import Link from "next/link";
import { notFound } from "next/navigation";
import { Story, StoryCard } from "@/components/StoryCard";
import { baseUrl } from "@/lib/api";
import { formatDateLong, parseDate } from "@/lib/date-utils";

interface ThreadStory extends Story {
  ref: string;
  date: string;
  sectionId: string;
  sectionTitle: string;
}

interface Thread {
  id: string;
  title: string;
  day: number;
  stories: ThreadStory[];
}

interface ThreadPageProps {
  params: Promise<{ id: string }>;
}

async function getThread(id: string): Promise<Thread | null> {
  try {
    const response = await fetch(`${baseUrl}/api/threads/${encodeURIComponent(id)}`, { cache: "no-store" });
    return response.ok ? (await response.json()).data : null;
  } catch (error) {
    console.error("Error fetching thread:", error);
    return null;
  }
}

export default async function ThreadPage({ params }: ThreadPageProps) {
  const { id } = await params;
  const thread = await getThread(id);
  if (!thread || thread.stories.length === 0) {
    notFound();
  }

  const first = thread.stories[0].date;
  const last = thread.stories[thread.stories.length - 1].date;
  const weekday = (date: string) => parseDate(date).toLocaleDateString("en-US", { weekday: "long" });

  return (
    <div className="diary-page" id="top" data-hero="classic">
      <header className="diary-hero">
        <div className="diary-hero-inner">
          <nav className="diary-crumbs">
            <Link href={`/diary/${last}`}>Latest entry</Link>
          </nav>
          <p className="diary-kicker">Story thread · day {thread.day}</p>
          <h1 className="diary-title">{thread.title}</h1>
          <p className="diary-summary">
            Followed over {thread.day} days, from {formatDateLong(first)} to {formatDateLong(last)}.
          </p>
        </div>
      </header>

      <ol className="diary-thread">
        {thread.stories.map((story, i) => (
          <li key={story.ref} className="diary-thread-day">
            <Link className="diary-thread-date" href={`/diary/${story.date}#${story.sectionId}`}>
              {weekday(story.date)}, {formatDateLong(story.date)} · {story.sectionTitle}
            </Link>
            <StoryCard story={story} card="timeline" index={i + 1} />
          </li>
        ))}
      </ol>
    </div>
  );
}

export async function generateMetadata({ params }: ThreadPageProps) {
  const { id } = await params;
  const thread = await getThread(id);
  return { title: thread ? `${thread.title} | Daily World Diary` : "Thread Not Found" };
}
