/**
 * Diary layout wrapper
 * Provides consistent layout structure with TOC sidebar and content area
 */

import { ReactNode } from "react";
import { TableOfContents } from "./TableOfContents";
import { TocItem } from "@/types";

interface DiaryLayoutProps {
  children: ReactNode;
  tocItems: TocItem[];
}

export function DiaryLayout({ children, tocItems }: DiaryLayoutProps) {
  return (
    <div className="container mx-auto px-4 py-8 lg:py-12">
      <div className="flex flex-col lg:flex-row gap-8 lg:gap-12">
        {/* Table of contents - top on mobile, right sidebar on desktop */}
        <aside className="lg:order-2">
          <TableOfContents items={tocItems} />
        </aside>

        {/* Main content area */}
        <main className="flex-1 lg:order-1 min-w-0 flex justify-center">
          <article className="w-full max-w-3xl">{children}</article>
        </main>
      </div>
    </div>
  );
}
