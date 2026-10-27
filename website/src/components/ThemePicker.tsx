"use client";

/**
 * Theme menu: stores the reader's choice in a cookie and re-renders, so the server applies it
 */

import { useRouter } from "next/navigation";
import { useState } from "react";
import { THEME_COOKIE, THEMES, ThemeId } from "@/lib/themes";

export function ThemePicker({ current }: { current: ThemeId }) {
  const router = useRouter();
  const [value, setValue] = useState(current);

  return (
    <label className="theme-picker">
      <span>Theme</span>
      <select
        value={value}
        onChange={(e) => {
          const theme = e.target.value as ThemeId;
          setValue(theme);
          document.cookie = `${THEME_COOKIE}=${theme}; path=/; max-age=31536000; samesite=lax`;
          router.refresh();
        }}
      >
        {THEMES.map((t) => (
          <option key={t.id} value={t.id}>
            {t.label}
          </option>
        ))}
      </select>
    </label>
  );
}
