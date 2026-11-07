import { useRef, useState, type KeyboardEvent } from "react";
import { Link } from "react-router-dom";
import {
  CheckCheck,
  ChevronDown,
  CircleAlert,
  ClipboardCheck,
  Mic,
  ShieldCheck,
} from "lucide-react";
import { Header } from "../components/Header";
import { IndustryScene } from "../components/IndustryScene";
import { industries } from "../lib/industries";
import { usePreferences } from "../lib/preferences";

export function Landing() {
  const { t } = usePreferences();
  const [selected, setSelected] = useState(0);
  const tabs = useRef<(HTMLButtonElement | null)[]>([]);
  const industry = industries[selected];
  const selectTab = (
    event: KeyboardEvent<HTMLButtonElement>,
    index: number,
  ) => {
    const key = event.key;
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(key)) return;
    event.preventDefault();
    const next =
      key === "Home"
        ? 0
        : key === "End"
          ? industries.length - 1
          : (index + (key === "ArrowRight" ? 1 : -1) + industries.length) %
            industries.length;
    setSelected(next);
    tabs.current[next]?.focus();
  };
  const steps = [
    {
      icon: Mic,
      title: t("Report naturally", "सहजता से रिपोर्ट करें"),
      description: t(
        "Record a short update. Inspect the transcript before extracting claims.",
        "एक छोटा अपडेट रिकॉर्ड करें। जानकारी निकालने से पहले लिखित विवरण जाँचें।",
      ),
    },
    {
      icon: CircleAlert,
      title: t("Keep the conditions", "स्थितियों को बनाए रखें"),
      description: t(
        "Packing complete and inspection pending remain separate reports.",
        "पैकिंग पूरी होने और निरीक्षण बाकी होने की रिपोर्ट अलग-अलग रहेंगी।",
      ),
    },
    {
      icon: ShieldCheck,
      title: t("Review the evidence", "सबूत की समीक्षा करें"),
      description: t(
        "An authorized person reviews the source and records their decision.",
        "एक अधिकृत व्यक्ति स्रोत की समीक्षा करके अपना निर्णय दर्ज करता है।",
      ),
    },
    {
      icon: ClipboardCheck,
      title: t("Acknowledge the version", "प्राप्त संस्करण की पुष्टि करें"),
      description: t(
        "The incoming shift acknowledges exactly what they received.",
        "अगली शिफ्ट ठीक उसी जानकारी की पुष्टि करती है जो उसे मिली है।",
      ),
    },
  ];

  return (
    <div className="landing-page">
      <Header marketing />
      <main id="main-content">
        <section
          className="hero marketing-container"
          aria-labelledby="hero-title"
        >
          <div className="hero-copy">
            <p className="eyebrow hero-eyebrow">
              <span aria-hidden="true">·</span>{" "}
              {t(
                "The next shift starts with clarity",
                "अगली शिफ्ट की शुरुआत स्पष्टता से",
              )}
            </p>
            <h1 id="hero-title">
              {t("Work changes hands.", "काम के हाथ बदलते हैं।")}
              <br />
              <em>{t("The details shouldn’t.", "विवरण नहीं बदलने चाहिए।")}</em>
            </h1>
            <p className="hero-description">
              {t(
                "Turn spoken updates into a handover people can trust. Keep unfinished work visible, resolve conflicting reports, and follow every decision back to its source.",
                "बोले गए अपडेट को भरोसेमंद हैंडओवर में बदलें। अधूरे काम पर नज़र रखें, विरोधाभासी रिपोर्ट सुलझाएँ और हर निर्णय का स्रोत जानें।",
              )}
            </p>
            <div className="hero-buttons">
              <Link to="/signup" className="button button-primary">
                {t("Build your workspace", "अपना कार्यस्थल बनाएँ")}
              </Link>
              <Link to="/signin" className="button button-outline">
                {t("Sign in", "साइन इन")}
              </Link>
            </div>
            <div className="hero-assurances">
              <span>
                {t("Hindi & Hinglish voice", "हिन्दी और हिंग्लिश आवाज़")}
              </span>
              <span>
                {t("Human-reviewed decisions", "मानव समीक्षा वाले निर्णय")}
              </span>
              <span>
                {t("Your organization’s workspace", "आपके संगठन का कार्यस्थल")}
              </span>
            </div>
          </div>
          <div className="motion-card">
            <div className="motion-heading">
              <span>
                {String(selected + 1).padStart(2, "0")} /{" "}
                {t("The handover in motion", "हैंडओवर की एक झलक")}
              </span>
              <span>{t("Illustrative scenario", "उदाहरण परिदृश्य")}</span>
            </div>
            <div className="scene-select">
              <select
                aria-label={t("Handover industry", "हैंडओवर उद्योग")}
                value={selected}
                onChange={(event) => setSelected(Number(event.target.value))}
              >
                {industries.map((item, index) => (
                  <option key={item.id} value={index}>
                    {t(item.name, item.hi)}
                  </option>
                ))}
              </select>
              <ChevronDown size={14} aria-hidden="true" />
            </div>
            <IndustryScene industry={industry.id} />
            <div className="scenario-report" aria-live="polite">
              <span className="report-icon">
                <CheckCheck size={19} />
              </span>
              <div>
                <span className="micro-label">
                  {t("Latest report", "नवीनतम रिपोर्ट")}
                </span>
                <strong>{t(industry.report, industry.reportHi)}</strong>
              </div>
              <span className="status-badge">
                {t("Reported", "रिपोर्ट किया गया")}
              </span>
            </div>
            <div className="scenario-condition" aria-live="polite">
              <CircleAlert size={16} />
              <div>
                <strong>{t(industry.condition, industry.conditionHi)}</strong>
                <p>
                  {t(
                    "A newer update doesn’t erase an unresolved condition.",
                    "नया अपडेट किसी अनसुलझी स्थिति को नहीं मिटाता।",
                  )}
                </p>
              </div>
            </div>
            <div className="motion-footer">
              <span>
                {t("Every update has a source.", "हर अपडेट का एक स्रोत।")}
              </span>
              <span>
                {t("Every shift has a next step.", "हर शिफ्ट का अगला कदम।")}
              </span>
            </div>
          </div>
        </section>

        <section
          id="industries"
          className="industries-section marketing-container"
          aria-labelledby="industries-title"
        >
          <div className="industries-intro">
            <div>
              <p className="eyebrow">
                {t(
                  "One principle. Different workplaces.",
                  "एक सिद्धांत। अलग-अलग कार्यस्थल।",
                )}
              </p>
              <h2 id="industries-title">
                {t("Built around the work", "आपके सौंपे जाने वाले")}
                <br />
                {t("you hand over.", "काम के लिए बना।")}
              </h2>
            </div>
            <p>
              {t(
                "Your organization type determines what you track, who reviews it, and what still needs verification.",
                "आपके संगठन का प्रकार तय करता है कि क्या ट्रैक करना है, कौन समीक्षा करेगा और किसकी पुष्टि अभी बाकी है।",
              )}
            </p>
          </div>
          <div
            className="industry-tabs"
            role="tablist"
            aria-label={t("Industries", "उद्योग")}
          >
            {industries.map((item, index) => (
              <button
                key={item.id}
                type="button"
                id={`tab-${item.id}`}
                ref={(element) => {
                  tabs.current[index] = element;
                }}
                role="tab"
                aria-selected={selected === index}
                aria-controls="industry-panel"
                tabIndex={selected === index ? 0 : -1}
                onClick={() => setSelected(index)}
                onKeyDown={(event) => selectTab(event, index)}
              >
                <strong>{t(item.name, item.hi)}</strong>
                <span>
                  {item.working
                    ? t("Working workflow", "कार्यशील प्रक्रिया")
                    : t("Planned workflow", "नियोजित प्रक्रिया")}
                </span>
              </button>
            ))}
          </div>
          <div
            className="industry-detail"
            id="industry-panel"
            role="tabpanel"
            tabIndex={0}
            aria-labelledby={`tab-${industry.id}`}
          >
            <span className="industry-number">
              {String(selected + 1).padStart(2, "0")}
            </span>
            <div>
              <h3>{t(industry.name, industry.hi)}</h3>
              <p>
                {t(industry.report, industry.reportHi)}. {t("But:", "लेकिन:")}{" "}
                <strong>{t(industry.condition, industry.conditionHi)}.</strong>
              </p>
              <p>
                {t("Next action:", "अगला कदम:")}{" "}
                {t(industry.action, industry.actionHi)}
              </p>
            </div>
            <span className="availability">
              {industry.working
                ? t("Available · private workspaces", "उपलब्ध · निजी कार्यस्थल")
                : t(
                    "Planned · future workflow",
                    "नियोजित · भविष्य की प्रक्रिया",
                  )}
            </span>
          </div>
        </section>

        <section
          id="how-it-works"
          className="how-section"
          aria-labelledby="how-title"
        >
          <div className="marketing-container">
            <p className="eyebrow">
              {t(
                "From a spoken update to a shared understanding",
                "बोले गए अपडेट से साझा समझ तक",
              )}
            </p>
            <h2 id="how-title">
              {t(
                "Say it. Check it. Carry it forward.",
                "कहें। जाँचें। आगे बढ़ाएँ।",
              )}
            </h2>
            <div className="steps-grid">
              {steps.map(({ icon: Icon, title, description }, index) => (
                <article className="step" key={index}>
                  <div className="step-heading">
                    <Icon size={22} strokeWidth={1.6} />
                    <span>{String(index + 1).padStart(2, "0")}</span>
                  </div>
                  <h3>{title}</h3>
                  <p>{description}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="closing-section marketing-container">
          <p className="eyebrow">
            {t(
              "Leave the next shift better informed",
              "अगली शिफ्ट को बेहतर जानकारी दें",
            )}
          </p>
          <h2>
            {t("The work continues.", "काम जारी रहता है।")}
            <br />
            {t("So should the context.", "जानकारी भी जारी रहनी चाहिए।")}
          </h2>
          <Link to="/signup" className="button button-primary">
            {t("Create your organization", "अपना संगठन बनाएँ")}
          </Link>
          <Link to="/signin" className="closing-signin">
            {t("Sign in", "साइन इन")}
          </Link>
        </section>
      </main>
    </div>
  );
}
