/**
 * Diary section component
 * Renders a numbered section as story cards in the card component and layout the day's theme picked
 */

import { CardStyle, DiarySection as DiarySectionType, StoryLayout, StoryThread } from "@/types";
import { MarketCharts } from "./MarketCharts";
import { StoryCard, splitStories } from "./StoryCard";

export const LAYOUTS: StoryLayout[] = ["stack", "grid-2", "grid-3", "feature", "masonry", "rail"];

interface DiarySectionProps {
  section: DiarySectionType;
  number: number;
  card: CardStyle;
  layout: StoryLayout;
  threads: StoryThread[];
}

export function DiarySection({ section, number, card, layout, threads }: DiarySectionProps) {
  return (
    <section
      className="diary-section"
      id={section.id}
      data-section={section.id}
      data-card={card}
      data-layout={layout}
    >
      <header className="diary-section-head">
        <span className="diary-section-number">{String(number).padStart(2, "0")}</span>
        <h2 className="diary-section-title">{section.title}</h2>
      </header>
      {section.charts && section.charts.length > 0 && <MarketCharts charts={section.charts} />}
      <div className={`diary-stories diary-stories--${layout}`}>
        {splitStories(section.content).map((story, i) => (
          <StoryCard
            key={i}
            story={story}
            card={card}
            index={i + 1}
            thread={threads.find((t) => t.story === `${section.id}/${i + 1}`)}
          />
        ))}
      </div>
    </section>
  );
}
