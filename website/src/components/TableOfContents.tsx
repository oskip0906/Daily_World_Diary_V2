"use client";

/**
 * Table of Contents component for diary navigation
 * Sticky sidebar on desktop, sticky horizontal strip on mobile; marks the section being read
 */

import { useEffect, useRef, useState } from "react";
import { TocItem } from "@/types";

interface TableOfContentsProps {
  items: TocItem[];
}

export function TableOfContents({ items }: TableOfContentsProps) {
  const [active, setActive] = useState(items[0]?.id);
  const strip = useRef<HTMLElement>(null);

  useEffect(() => {
    // a section is "being read" while it crosses a band just below the top of the screen
    const observer = new IntersectionObserver(
      (entries) => {
        const hit = entries.find((e) => e.isIntersecting);
        if (hit) setActive(hit.target.id);
      },
      { rootMargin: "-15% 0px -70% 0px" }
    );
    items.forEach((item) => {
      const element = document.getElementById(item.id);
      if (element) observer.observe(element);
    });
    return () => observer.disconnect();
  }, [items]);

  useEffect(() => {
    // on the mobile strip, keep the active link in view (scrollIntoView would interrupt page scrolling)
    const container = strip.current;
    const link = container?.querySelector<HTMLElement>(".is-active");
    if (container && link && container.scrollWidth > container.clientWidth) {
      container.scrollTo({ left: link.offsetLeft - 16, behavior: "smooth" });
    }
  }, [active]);

  return (
    <aside className="diary-toc" ref={strip}>
      <nav className="diary-toc-nav" aria-label="Table of contents">
        <p className="diary-toc-label">In this edition</p>
        <ol className="diary-toc-list">
          {items.map((item, i) => (
            <li key={item.id}>
              <a
                href={`#${item.id}`}
                className={`diary-toc-link${item.id === active ? " is-active" : ""}`}
                aria-current={item.id === active ? "true" : undefined}
              >
                <span className="diary-toc-number">{String(i + 1).padStart(2, "0")}</span> {item.title}
              </a>
            </li>
          ))}
        </ol>
        <a className="diary-toc-top" href="#top">
          ↑ Back to top
        </a>
        <a className="diary-toc-bottom" href="#bottom">
          ↓ Go to bottom
        </a>
      </nav>
    </aside>
  );
}
