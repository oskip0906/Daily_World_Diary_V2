/**
 * MDX content renderer
 * Wraps markdown/MDX content in prose styling for consistent typography
 */

interface MDXContentProps {
  content: string;
}

export function MDXContent({ content }: MDXContentProps) {
  // In production, this would use @mdx-js/react's evaluate or compile
  // For now, render as HTML with dangerouslySetInnerHTML
  // This allows the mocked API to return simple markdown that gets styled
  return (
    <div
      className="mdx-content"
      dangerouslySetInnerHTML={{ __html: content }}
    />
  );
}
