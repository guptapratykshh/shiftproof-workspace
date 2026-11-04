import { Link } from "react-router-dom";
import { Building2, ClipboardCheck, HardHat } from "lucide-react";
import { Header } from "../components/Header";
import { usePreferences } from "../lib/preferences";

export function SignIn() {
  const { t } = usePreferences();
  const roles = [
    {
      id: "worker",
      icon: HardHat,
      title: t("Sign in as a worker", "कर्मचारी के रूप में साइन इन"),
      description: t(
        "Send spoken updates and see your assigned work.",
        "बोलकर अपडेट भेजें और अपना सौंपा गया काम देखें।",
      ),
    },
    {
      id: "supervisor",
      icon: ClipboardCheck,
      title: t("Sign in as a supervisor", "पर्यवेक्षक के रूप में साइन इन"),
      description: t(
        "Check your team’s reports and prepare the next handover.",
        "अपनी टीम की रिपोर्ट जाँचें और अगला हैंडओवर तैयार करें।",
      ),
    },
    {
      id: "organization",
      icon: Building2,
      title: t("Sign in as an organisation", "संगठन के रूप में साइन इन"),
      description: t(
        "Manage your organisation, people and workplace settings.",
        "अपने संगठन, लोगों और कार्यस्थल की सेटिंग्स का प्रबंधन करें।",
      ),
    },
  ];
  return (
    <div className="auth-page">
      <Header />
      <main id="main-content" className="signin-main">
        <div className="signin-intro">
          <p className="auth-eyebrow">{t("Welcome back", "वापस स्वागत है")}</p>
          <h1>
            {t(
              "How would you like to sign in?",
              "आप कैसे साइन इन करना चाहेंगे?",
            )}
          </h1>
          <p className="page-description">
            {t(
              "Choose how you work with your team.",
              "अपनी टीम में अपनी भूमिका चुनें।",
            )}
          </p>
        </div>
        <div className="role-grid">
          {roles.map(({ id, icon: Icon, title, description }) => (
            <article className="role-card" key={id}>
              <div className="role-icon">
                <Icon strokeWidth={1.8} />
              </div>
              <h2>{title}</h2>
              <p>{description}</p>
              <Link
                to={`/signin/${id}`}
                className="button button-primary"
                aria-label={`${t("Continue", "जारी रखें")}: ${title}`}
              >
                {t("Continue", "जारी रखें")}
              </Link>
            </article>
          ))}
        </div>
        <p className="auth-switch">
          {t("New to ShiftProof?", "ShiftProof पर नए हैं?")}{" "}
          <Link to="/signup">
            {t("Create an organization", "एक संगठन बनाएँ")}
          </Link>
        </p>
        <Link className="back-home" to="/">
          {t("Back to ShiftProof", "ShiftProof पर वापस जाएँ")}
        </Link>
      </main>
    </div>
  );
}
