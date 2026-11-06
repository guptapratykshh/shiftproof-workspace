import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

export type Theme = "dark" | "light";
type Language = "en" | "hi";
type Preferences = {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  language: Language;
  toggleLanguage: () => void;
  t: (english: string, hindi: string) => string;
};

const PreferencesContext = createContext<Preferences | null>(null);

function saved<T extends string>(
  key: string,
  allowed: readonly T[],
  fallback: T,
): T {
  try {
    const value = localStorage.getItem(key) as T;
    return allowed.includes(value) ? value : fallback;
  } catch {
    return fallback;
  }
}

function persist(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* Preferences still work for this session. */
  }
}

export function PreferencesProvider({ children }: { children: ReactNode }) {
  const [theme, updateTheme] = useState<Theme>(() => {
    const previous = saved(
      "shiftproof-theme",
      ["dark", "light", "system"],
      "light",
    );
    // Retain the visible appearance when migrating an older System preference.
    return previous === "system"
      ? matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light"
      : previous;
  });
  const [language, setLanguage] = useState<Language>(() =>
    saved("shiftproof-language", ["en", "hi"], "en"),
  );
  const t = useCallback(
    (english: string, hindi: string) => (language === "hi" ? hindi : english),
    [language],
  );

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    const background = getComputedStyle(document.documentElement)
      .getPropertyValue("--background")
      .trim();
    document
      .querySelector('meta[name="theme-color"]')
      ?.setAttribute("content", background);
    persist("shiftproof-theme", theme);
  }, [theme]);

  useEffect(() => {
    document.documentElement.lang = language;
    persist("shiftproof-language", language);
  }, [language]);

  return (
    <PreferencesContext.Provider
      value={{
        theme,
        setTheme: updateTheme,
        language,
        toggleLanguage: () =>
          setLanguage((value) => (value === "en" ? "hi" : "en")),
        t,
      }}
    >
      {children}
    </PreferencesContext.Provider>
  );
}

export function usePreferences() {
  const context = useContext(PreferencesContext);
  if (!context) throw new Error("PreferencesProvider is required");
  return context;
}
