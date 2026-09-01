import { useState, useEffect } from "react";

const DARK_QUERY = "(prefers-color-scheme: dark)";

// Resolves the user's preference ("light" | "dark" | "system") into the theme
// actually painted. The resolved value is derived during render rather than
// pushed through an effect, so there is no cascading second render, and the
// subscription means a change to the OS theme reaches a "system" user live.
export function useTheme(initial = "system") {
  const [themeSetting, setThemeSetting] = useState(initial);
  const [systemPrefersDark, setSystemPrefersDark] = useState(
    () => window.matchMedia(DARK_QUERY).matches
  );

  useEffect(() => {
    const mq = window.matchMedia(DARK_QUERY);
    const onChange = (e) => setSystemPrefersDark(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const activeTheme =
    themeSetting === "system" ? (systemPrefersDark ? "dark" : "light") : themeSetting;

  const toggleTheme = () => setThemeSetting(activeTheme === "dark" ? "light" : "dark");

  return { themeSetting, setThemeSetting, activeTheme, toggleTheme };
}
