/**
 * Diary section component
 * Renders a single content section with heading and MDX content
 */

import { DiarySection as DiarySectionType } from "@/types";
import { MDXContent } from "./MDXContent";

interface DiarySectionProps {
  section: DiarySectionType;
}

export function DiarySection({ section }: DiarySectionProps) {
  return (
    <section
      id={section.id}
      className="scroll-mt-8 py-8 border-b border-border dark:border-dark-border last:border-b-0"
    >
      <h2 className="text-2xl md:text-3xl font-semibold text-text-primary dark:text-dark-text-primary mb-6">
        {section.title}
      </h2>
      <div className="prose prose-lg dark:prose-invert max-w-none">
        <MDXContent content={section.content} />

        {section.sources && section.sources.length > 0 && (
          <>
            <hr className="my-8" />
            <h3>Sources</h3>
            <ul>
              {section.sources.map((source) => (
                <li key={source.url}>
                  <a
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {source.title}
                  </a>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </section>
  );
}
