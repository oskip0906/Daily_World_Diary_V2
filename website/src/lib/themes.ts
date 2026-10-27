/**
 * Home page themes: "auto" follows the system light/dark setting; the others are fixed palettes
 * (globals.css, [data-theme]). The choice lives in a cookie so the server renders it with no flash.
 * Diary pages always show the day's own design.
 */

export const THEMES = [
  { id: "auto", label: "Auto" },
  { id: "light", label: "Light" },
  { id: "dark", label: "Dark" },
  { id: "sepia", label: "Sepia" },
  { id: "midnight", label: "Midnight" },
  { id: "contrast", label: "High contrast" },
] as const;

export type ThemeId = (typeof THEMES)[number]["id"];

export const THEME_COOKIE = "diary-theme";

// the cookie is user-controlled: anything unknown is the default
export function readTheme(value: string | undefined): ThemeId {
  return THEMES.find((t) => t.id === value)?.id ?? "auto";
}
