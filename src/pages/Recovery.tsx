import { useState, type FormEvent } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  CircleAlert,
  KeyRound,
  LoaderCircle,
  Mail,
} from "lucide-react";
import { Header } from "../components/Header";
import { FormField } from "../components/FormField";
import { usePreferences } from "../lib/preferences";
import { authErrorMessage, requestAuth, type AuthResult } from "../lib/auth";

export function Recovery() {
  const { role } = useParams();
  const { t } = usePreferences();
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<AuthResult | null>(null);
  const [error, setError] = useState("");
  if (!role || !["worker", "supervisor", "organization"].includes(role))
    return <Navigate to="/signin" replace />;
  const worker = role === "worker";
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setError("");
    setBusy(true);
    try {
      const response = await requestAuth("recover", {
        email: String(data.get("email")),
        role,
        ...(role === "supervisor"
          ? { organizationId: String(data.get("organizationId")) }
          : {}),
      });
      setResult(response);
    } catch (cause) {
      setError(authErrorMessage(cause, t));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="auth-page">
      <Header />
      <main id="main-content" className="login-main">
        <Link className="back-to-roles" to={`/signin/${role}`}>
          <ArrowLeft size={16} />
          {t("Back to sign in", "साइन इन पर वापस जाएँ")}
        </Link>
        <div className="form-intro">
          <div className="role-icon">
            <KeyRound />
          </div>
          <p className="auth-eyebrow">
            {t("A little help getting back in", "वापस आने के लिए थोड़ी मदद")}
          </p>
          <h1>
            {worker
              ? t("Reset your PIN.", "अपना पिन रीसेट करें।")
              : t("Forgot your password?", "पासवर्ड भूल गए?")}
          </h1>
        </div>
        {worker ? (
          <section className="form-card recovery-help">
            <h2>
              {t("Contact your supervisor", "अपने पर्यवेक्षक से संपर्क करें")}
            </h2>
            <p>
              {t(
                "Your supervisor or organization admin can help you securely reset your PIN after verifying your identity. Have your Organization ID and Employee ID ready.",
                "पहचान सत्यापित करने के बाद आपके पर्यवेक्षक या संगठन प्रशासक पिन सुरक्षित रूप से रीसेट करने में मदद करेंगे। अपनी संगठन आईडी और कर्मचारी आईडी तैयार रखें।",
              )}
            </p>
            <p>
              {t(
                "You don’t need an email address to access your worker account.",
                "कर्मचारी खाते के लिए ईमेल की ज़रूरत नहीं है।",
              )}
            </p>
            <Link to="/signin/worker" className="button button-primary">
              {t("Return to sign in", "साइन इन पर वापस जाएँ")}
            </Link>
          </section>
        ) : result ? (
          <section className="form-card success-card" role="status">
            <Mail />
            <h2>
              {result.delivery === "local_outbox"
                ? t("Recovery requested locally", "रिकवरी का अनुरोध स्थानीय रूप से प्राप्त हुआ")
                : t("Recovery requested", "रिकवरी का अनुरोध प्राप्त हुआ")}
            </h2>
            <p>
              {result.delivery === "local_outbox"
                ? t(
                    "Email delivery is in local development mode. If an account matches these details, its reset message will be saved in backend/data/outbox. No email will arrive in your inbox.",
                    "ईमेल अभी स्थानीय विकास मोड में है। यदि इस जानकारी से खाता मिलता है, तो रीसेट संदेश backend/data/outbox में सहेजा जाएगा। इनबॉक्स में ईमेल नहीं आएगा।",
                  )
                : t(
                    "If an account matches these details, a password reset email will be queued for delivery. Check your inbox and spam folder shortly.",
                    "यदि इस जानकारी से खाता मिलता है, तो पासवर्ड रीसेट ईमेल भेजने की कतार में जोड़ा जाएगा। थोड़ी देर में इनबॉक्स और स्पैम फ़ोल्डर जाँचें।",
                  )}
            </p>
          </section>
        ) : (
          <form className="form-card login-form" onSubmit={submit}>
            <p>
              {t(
                "Enter your account details and we’ll send you a reset link.",
                "अपने खाते का विवरण भरें और हम रीसेट लिंक भेजेंगे।",
              )}
            </p>
            {role === "supervisor" && (
              <FormField
                name="organizationId"
                id="recovery-org"
                label={t("Organization ID", "संगठन आईडी")}
                required
              />
            )}
            <FormField
              name="email"
              id="recovery-email"
              label={t("Email address", "ईमेल पता")}
              type="email"
              autoComplete="email"
              required
            />
            {error && (
              <div className="form-alert" role="alert">
                <CircleAlert size={19} />
                <p>{error}</p>
              </div>
            )}
            <button
              className="button button-primary form-submit"
              type="submit"
              disabled={busy}
            >
              {busy && <LoaderCircle size={18} className="spin" />}
              {t("Send reset link", "रीसेट लिंक भेजें")}
            </button>
          </form>
        )}
      </main>
    </div>
  );
}
