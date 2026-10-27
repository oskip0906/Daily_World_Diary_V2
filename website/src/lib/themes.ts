/**
 * Reader themes: "daily" shows the day's generated design; the others replace it with a fixed palette
 * (globals.css). The choice lives in a cookie so the server renders the right one with no flash.
 */

export const THEMES = [
  { id: "daily", label: "Today's design" },
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
  return THEMES.find((t) => t.id === value)?.id ?? "daily";
}
