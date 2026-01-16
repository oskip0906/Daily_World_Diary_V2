"use client";

/**
 * Collapsible panel component
 * Generic accordion-style component for expandable content
 */

import { useState, ReactNode } from "react";

interface CollapsiblePanelProps {
  title: string;
  subtitle?: string;
  children: ReactNode;
  defaultOpen?: boolean;
}

export function CollapsiblePanel({
  title,
  subtitle,
  children,
  defaultOpen = false,
}: CollapsiblePanelProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="border border-border dark:border-dark-border rounded-lg overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-4 py-3 flex items-center justify-between bg-bg-secondary dark:bg-dark-bg-secondary hover:bg-bg-tertiary dark:hover:bg-dark-bg-tertiary transition-colors"
        aria-expanded={isOpen}
      >
        <div className="text-left">
          <h4 className="text-sm font-semibold text-text-primary dark:text-dark-text-primary">
            {title}
          </h4>
          {subtitle && (
            <p className="text-xs text-text-muted dark:text-dark-text-muted mt-0.5">
              {subtitle}
            </p>
          )}
        </div>
        <svg
          className={`w-5 h-5 text-text-secondary dark:text-dark-text-secondary transition-transform ${
            isOpen ? "rotate-180" : ""
          }`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </button>

      {isOpen && (
        <div className="px-4 py-3 bg-white dark:bg-dark-bg-primary">
          {children}
        </div>
      )}
    </div>
  );
}
