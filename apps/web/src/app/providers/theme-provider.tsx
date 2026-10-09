import { useEffect, type ReactNode } from "react";
import { useSettings } from "@/services/queries";
import type { Theme } from "@/types/api";

export const THEME_KEY = "hub-theme";

export function applyTheme(theme: Theme) {
  const dark = theme === "dark" || (theme === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", dark);
}

/** La fuente de verdad es el backend; localStorage solo evita el parpadeo inicial. */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const { data } = useSettings();
  const theme = data?.theme;
  useEffect(() => {
    if (!theme) return;
    try { localStorage.setItem(THEME_KEY, theme); } catch { /* almacenamiento no disponible */ }
    applyTheme(theme);
    if (theme !== "system") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const on = () => applyTheme("system");
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, [theme]);
  return <>{children}</>;
}
