/**
 * Root layout component
 * Provides global HTML structure, metadata, and persistent UI elements
 */

import type { Metadata } from "next";
import {
  Bebas_Neue,
  Fraunces,
  IBM_Plex_Mono,
  Inter,
  Newsreader,
  Playfair_Display,
  Space_Grotesk,
} from "next/font/google";
import "./globals.css";

// Each day's theme picks from these by variable (FONTS in backend/diary/design.py); keep the two in
// step. Only the base design's three preload, the rest download when a theme uses them.
const fraunces = Fraunces({ subsets: ["latin"], variable: "--ff-fraunces", display: "swap" });
const newsreader = Newsreader({ subsets: ["latin"], variable: "--ff-newsreader", style: ["normal", "italic"], display: "swap" });
const inter = Inter({ subsets: ["latin"], variable: "--ff-inter", display: "swap" });
const playfair = Playfair_Display({ subsets: ["latin"], variable: "--ff-playfair", display: "swap", preload: false });
const spaceGrotesk = Space_Grotesk({ subsets: ["latin"], variable: "--ff-space-grotesk", display: "swap", preload: false });
const plexMono = IBM_Plex_Mono({ subsets: ["latin"], weight: ["400", "600"], variable: "--ff-plex-mono", display: "swap", preload: false });
const bebas = Bebas_Neue({ subsets: ["latin"], weight: "400", variable: "--ff-bebas", display: "swap", preload: false });
const fontVariables = [fraunces, newsreader, inter, playfair, spaceGrotesk, plexMono, bebas]
  .map((f) => f.variable)
  .join(" ");

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
    <html lang="en" className={`smooth-scroll ${fontVariables}`}>
      <body className="flex flex-col min-h-screen">
        <div className="flex-1">{children}</div>
      </body>
    </html>
  );
}
