/**
 * Diary section component
 * Renders a single numbered section; its HTML is sanitized by the backend (backend/diary/render.py)
 */

import { DiarySection as DiarySectionType } from "@/types";

// Entries before 2026-10-26 end sentences with citation links; the only <a> tags the backend ever wrote
const CITATION_LINK = /\s*<a [^>]*>[^<]*<\/a>/g;

interface DiarySectionProps {
  section: DiarySectionType;
  number: number;
}

export function DiarySection({ section, number }: DiarySectionProps) {
  return (
    <section className="diary-section" id={section.id} data-section={section.id}>
      <header className="diary-section-head">
        <span className="diary-section-number">{String(number).padStart(2, "0")}</span>
        <h2 className="diary-section-title">{section.title}</h2>
      </header>
      <div
        className="diary-prose"
        dangerouslySetInnerHTML={{ __html: section.content.replace(CITATION_LINK, "") }}
      />
    </section>
  );
}
