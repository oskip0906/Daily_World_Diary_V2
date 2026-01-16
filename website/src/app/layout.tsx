/**
 * Root layout component
 * Provides global HTML structure, metadata, and persistent UI elements
 */

import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Daily World Diary — Automated AI Journal",
  description:
    "An AI-generated daily snapshot of global events across politics, finance, entertainment, music, and markets. Exploring the world through automated journalism.",
  keywords: [
    "AI journalism",
    "daily news",
    "world events",
    "automated reporting",
    "global news",
    "market analysis",
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="smooth-scroll">
      <body className="flex flex-col min-h-screen">
        <div className="flex-1">{children}</div>
      </body>
    </html>
  );
}
