import { Link } from "react-router-dom";
import { Moon, Sun } from "lucide-react";
import { usePreferences } from "../lib/preferences";

export function Brand() {
  return (
    <Link to="/" className="brand" aria-label="ShiftProof home">
      <span className="brand-mark" aria-hidden="true">
        <svg viewBox="0 0 40 40">
          <path d="m8 22 5 5L25 13M19 25l3 3 10-13" />
        </svg>
      </span>
      <span>
        shiftproof<span className="brand-dot">.</span>
      </span>
    </Link>
  );
}

export function Header({ marketing = false }: { marketing?: boolean }) {
  const { theme, setTheme, toggleLanguage, language, t } = usePreferences();
  const themeAction = theme === "dark"
    ? t("Switch to light theme", "हल्की थीम पर जाएँ")
    : t("Switch to dark theme", "गहरी थीम पर जाएँ");

  return (
    <header
      className={`site-header ${marketing ? "marketing-header" : "auth-header"}`}
    >
      <a href="#main-content" className="skip-link">
        {t("Skip to content", "मुख्य सामग्री पर जाएँ")}
      </a>
      <div className="header-inner">
        <Brand />
        {marketing && (
          <nav
            className="marketing-nav"
            aria-label={t("Main navigation", "मुख्य नेविगेशन")}
          >
            <a href="#industries">{t("Industries", "उद्योग")}</a>
            <a href="#how-it-works">
              {t("How it works", "यह कैसे काम करता है")}
            </a>
          </nav>
        )}
        <div className="header-actions">
          <button
            type="button"
            className="language-toggle"
            onClick={toggleLanguage}
            aria-label={
              language === "en" ? "Switch to Hindi" : "Switch to English"
            }
          >
            {language === "en" ? "हिन्दी" : "English"}
          </button>
          <button
            type="button"
            className="theme-toggle"
            aria-label={themeAction}
            title={themeAction}
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          >
            {theme === "dark" ? <Sun aria-hidden="true" /> : <Moon aria-hidden="true" />}
          </button>
          {marketing && (
            <>
              <Link className="header-signin" to="/signin">
                {t("Sign in", "साइन इन")}
              </Link>
              <Link className="button button-primary header-cta" to="/signup">
                {t("Create organization", "संगठन बनाएँ")}
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
