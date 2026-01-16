/**
 * MDX Components configuration
 * Customizes how MDX elements are rendered throughout the application
 * Can be extended to add custom components or styling
 */

import type { MDXComponents } from "mdx/types";

export function useMDXComponents(components: MDXComponents): MDXComponents {
  return {
    // Customize heading components
    h1: ({ children }) => (
      <h1 className="text-3xl font-bold text-text-primary dark:text-dark-text-primary mb-4">
        {children}
      </h1>
    ),
    h2: ({ children }) => (
      <h2 className="text-2xl font-semibold text-text-primary dark:text-dark-text-primary mt-8 mb-4">
        {children}
      </h2>
    ),
    h3: ({ children }) => (
      <h3 className="text-xl font-semibold text-text-primary dark:text-dark-text-primary mt-6 mb-3">
        {children}
      </h3>
    ),

    // Customize paragraph and text elements
    p: ({ children }) => (
      <p className="text-text-secondary dark:text-dark-text-secondary leading-relaxed mb-4">
        {children}
      </p>
    ),

    // Customize lists
    ul: ({ children }) => (
      <ul className="list-disc list-inside mb-4 space-y-2 text-text-secondary dark:text-dark-text-secondary">
        {children}
      </ul>
    ),
    ol: ({ children }) => (
      <ol className="list-decimal list-inside mb-4 space-y-2 text-text-secondary dark:text-dark-text-secondary">
        {children}
      </ol>
    ),

    // Customize links
    a: ({ href, children }) => (
      <a
        href={href}
        className="text-accent dark:text-dark-accent hover:text-accent-hover dark:hover:text-dark-accent-hover underline"
        target={href?.startsWith("http") ? "_blank" : undefined}
        rel={href?.startsWith("http") ? "noopener noreferrer" : undefined}
      >
        {children}
      </a>
    ),

    // Customize code blocks
    code: ({ children }) => (
      <code className="bg-bg-secondary dark:bg-dark-bg-secondary px-1.5 py-0.5 rounded text-sm font-mono">
        {children}
      </code>
    ),

    // Allow custom components to be passed in
    ...components,
  };
}
