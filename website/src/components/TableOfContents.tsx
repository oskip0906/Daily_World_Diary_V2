"use client";

/**
 * Table of Contents component for diary navigation
 * Sticky sidebar on desktop, collapsible on mobile
 */

import { TocItem } from "@/types";

interface TableOfContentsProps {
  items: TocItem[];
}

export function TableOfContents({ items }: TableOfContentsProps) {
  const handleClick = (id: string) => {
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  return (
    <nav
      className="w-full lg:w-64 lg:sticky lg:top-4 lg:self-start"
      aria-label="Table of contents"
    >
      <div className="bg-bg-secondary dark:bg-dark-bg-secondary border border-border dark:border-dark-border rounded-lg p-4">
        <h3 className="text-sm font-semibold text-text-primary dark:text-dark-text-primary uppercase tracking-wider mb-3">
          Contents
        </h3>
        <ul className="space-y-2">
          {items
            .sort((a, b) => a.order - b.order)
            .map((item) => (
              <li key={item.id}>
                <button
                  onClick={() => handleClick(item.id)}
                  className="text-sm text-text-secondary dark:text-dark-text-secondary hover:text-accent dark:hover:text-dark-accent transition-colors text-left w-full"
                >
                  {item.title}
                </button>
              </li>
            ))}
        </ul>
      </div>
    </nav>
  );
}
