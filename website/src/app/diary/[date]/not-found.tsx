/**
 * Not found page for missing diary entries
 */

import Link from "next/link";

export default function NotFound() {
  return (
    <div className="container mx-auto px-4 py-16">
      <div className="max-w-2xl mx-auto text-center">
        <h1 className="text-4xl md:text-5xl font-bold text-text-primary dark:text-dark-text-primary mb-4">
          Entry Not Found
        </h1>
        <p className="text-lg text-text-secondary dark:text-dark-text-secondary mb-8">
          No diary entry exists for this date. The entry may not have been
          generated yet, or the date may be invalid.
        </p>
        <Link
          href="/"
          className="inline-flex items-center justify-center px-6 py-3 bg-accent dark:bg-dark-accent text-white rounded-lg hover:bg-accent-hover dark:hover:bg-dark-accent-hover transition-colors"
        >
          ← Return to Calendar
        </Link>
      </div>
    </div>
  );
}
