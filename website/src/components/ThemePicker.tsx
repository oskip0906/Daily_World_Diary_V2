"use client";

/**
 * Home page theme swatches. Each previews its own palette (it carries data-theme). A click sets the
 * theme on the page directly, with no server round trip, and saves it in a cookie for the next visit.
 */

import { useState } from "react";
import { THEME_COOKIE, THEMES, ThemeId } from "@/lib/themes";

export function ThemePicker({ current }: { current: ThemeId }) {
  const [value, setValue] = useState(current);

  return (
    <div className="theme-swatches" role="radiogroup" aria-label="Theme">
      {THEMES.map((t) => (
        <button
          key={t.id}
          type="button"
          role="radio"
          aria-checked={value === t.id}
          className="theme-swatch"
          data-theme={t.id}
          title={t.label}
          onClick={(e) => {
            setValue(t.id);
            e.currentTarget.closest(".home")?.setAttribute("data-theme", t.id);
            document.cookie = `${THEME_COOKIE}=${t.id}; path=/; max-age=31536000; samesite=lax`;
          }}
        >
          <span className="theme-swatch-dot" aria-hidden="true" />
          <span className="theme-swatch-label">{t.label}</span>
        </button>
      ))}
    </div>
  );
}
