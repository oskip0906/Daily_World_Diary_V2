"use client";

/**
 * Home page theme swatches: each previews its own palette (it carries data-theme), stores the choice
 * in a cookie and re-renders, so the server applies it
 */

import { useRouter } from "next/navigation";
import { useState } from "react";
import { THEME_COOKIE, THEMES, ThemeId } from "@/lib/themes";

export function ThemePicker({ current }: { current: ThemeId }) {
  const router = useRouter();
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
          data-theme={t.id === "auto" ? undefined : t.id}
          title={t.label}
          onClick={() => {
            setValue(t.id);
            document.cookie = `${THEME_COOKIE}=${t.id}; path=/; max-age=31536000; samesite=lax`;
            router.refresh();
          }}
        >
          <span className="theme-swatch-dot" aria-hidden="true" />
          <span className="theme-swatch-label">{t.label}</span>
        </button>
      ))}
    </div>
  );
}
