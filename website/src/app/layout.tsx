/**
 * Root layout component
 * Provides global HTML structure, metadata, and persistent UI elements
 */

import type { Metadata } from "next";
import { cookies } from "next/headers";
import {
  Archivo_Black,
  Bebas_Neue,
  DM_Serif_Display,
  Fraunces,
  IBM_Plex_Mono,
  Instrument_Serif,
  Inter,
  Newsreader,
  Playfair_Display,
  Space_Grotesk,
  Syne,
  Unbounded,
} from "next/font/google";
import { ThemePicker } from "@/components/ThemePicker";
import { THEME_COOKIE, readTheme } from "@/lib/themes";
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
const dmSerif = DM_Serif_Display({ subsets: ["latin"], weight: "400", style: ["normal", "italic"], variable: "--ff-dm-serif", display: "swap", preload: false });
const instrument = Instrument_Serif({ subsets: ["latin"], weight: "400", style: ["normal", "italic"], variable: "--ff-instrument", display: "swap", preload: false });
const syne = Syne({ subsets: ["latin"], variable: "--ff-syne", display: "swap", preload: false });
const unbounded = Unbounded({ subsets: ["latin"], variable: "--ff-unbounded", display: "swap", preload: false });
const archivoBlack = Archivo_Black({ subsets: ["latin"], weight: "400", variable: "--ff-archivo-black", display: "swap", preload: false });
const fontVariables = [
  fraunces, newsreader, inter, playfair, spaceGrotesk, plexMono, bebas,
  dmSerif, instrument, syne, unbounded, archivoBlack,
]
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

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const theme = readTheme((await cookies()).get(THEME_COOKIE)?.value);
  return (
    <html lang="en" className={`smooth-scroll ${fontVariables}`} data-theme={theme === "daily" ? undefined : theme}>
      <body className="flex flex-col min-h-screen">
        <div className="flex-1">{children}</div>
        <ThemePicker current={theme} />
      </body>
    </html>
  );
}
