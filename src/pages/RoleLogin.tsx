import { useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  ArrowLeft,
  Building2,
  CircleAlert,
  ClipboardCheck,
  HardHat,
  LoaderCircle,
  ShieldCheck,
} from "lucide-react";
import { Header } from "../components/Header";
import { FormField } from "../components/FormField";
import { usePreferences } from "../lib/preferences";
import { authErrorMessage, requestAuth, type AuthRole } from "../lib/auth";

type LoginValues = {
  organizationId: string;
  email: string;
  employeeId: string;
  password: string;
  pin: string;
};

export function RoleLogin() {
  const { role } = useParams();
  if (!role || !["worker", "supervisor", "organization"].includes(role))
    return <Navigate to="/signin" replace />;
  return <LoginForm key={role} role={role as AuthRole} />;
}

function LoginForm({ role }: { role: AuthRole }) {
  const { t } = usePreferences();
  const [error, setError] = useState("");
  const [signedIn, setSignedIn] = useState(false);
  const worker = role === "worker";
  const supervisor = role === "supervisor";
  const Icon = worker ? HardHat : supervisor ? ClipboardCheck : Building2;
  const schema = z.object({
    organizationId:
      worker || supervisor
        ? z
            .string()
            .trim()
            .min(1, t("Enter your Organization ID.", "अपनी संगठन आईडी भरें।"))
        : z.string(),
    employeeId: worker
      ? z
          .string()
          .trim()
          .min(1, t("Enter your Employee ID.", "अपनी कर्मचारी आईडी भरें।"))
      : z.string(),
    email: worker
      ? z.string()
      : z.email(t("Enter a valid email address.", "एक मान्य ईमेल भरें।")),
    pin: worker
      ? z
          .string()
          .regex(
            /^\d{6}$/,
            t("Enter your 6-digit PIN.", "अपना 6 अंकों का पिन भरें।"),
          )
      : z.string(),
    password: worker
      ? z.string()
      : z.string().min(1, t("Enter your password.", "अपना पासवर्ड भरें।")),
  });
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      organizationId: "",
      employeeId: "",
      email: "",
      pin: "",
      password: "",
    },
  });
  const submit = async (values: LoginValues) => {
    setError("");
    try {
      const payload = Object.fromEntries(
        Object.entries(values).filter(([, value]) => value !== ""),
      );
      const result = await requestAuth("login", payload, role);
      try {
        localStorage.removeItem("shiftproof-locked");
      } catch {
        /* No local preference storage. */
      }
      // Only follow an API-provided same-origin workspace path; never an arbitrary URL.
      if (
        result.redirectPath?.startsWith("/workspace") &&
        !result.redirectPath.includes("\\")
      )
        window.location.assign(result.redirectPath);
      else setSignedIn(true);
    } catch (cause) {
      setError(authErrorMessage(cause, t, "login"));
    }
  };
  return (
    <div className="auth-page">
      <Header />
      <main id="main-content" className="login-main">
        <Link className="back-to-roles" to="/signin">
          <ArrowLeft size={16} />
          {t("All sign-in options", "सभी साइन-इन विकल्प")}
        </Link>
        <div className="form-intro">
          <div className="role-icon">
            <Icon strokeWidth={1.8} />
          </div>
          <p className="auth-eyebrow">{t("Welcome back", "वापस स्वागत है")}</p>
          <h1>
            {worker
              ? t(
                  "Your next shift starts here.",
                  "आपकी अगली शिफ्ट यहीं शुरू होती है।",
                )
              : supervisor
                ? t("Keep your team connected.", "अपनी टीम को जोड़े रखें।")
                : t(
                    "Welcome to your workspace.",
                    "अपने कार्यस्थल में आपका स्वागत है।",
                  )}
          </h1>
          <p className="page-description">
            {worker
              ? t(
                  "Sign in with your organization, employee ID and PIN.",
                  "संगठन आईडी, कर्मचारी आईडी और पिन से साइन इन करें।",
                )
              : supervisor
                ? t(
                    "Sign in to review, coordinate and carry work forward.",
                    "समीक्षा, समन्वय और काम आगे बढ़ाने के लिए साइन इन करें।",
                  )
                : t(
                    "Manage your organization with a clearer picture.",
                    "स्पष्ट जानकारी के साथ अपने संगठन का प्रबंधन करें।",
                  )}
          </p>
        </div>
        {signedIn ? (
          <section className="form-card success-card" role="status">
            <ShieldCheck />
            <h2>{t("You’re signed in.", "आपने साइन इन कर लिया है।")}</h2>
            <p>
              {t(
                "Your account is verified. Contact your administrator for your workspace address.",
                "आपका खाता सत्यापित है। कार्यस्थल के पते के लिए अपने प्रशासक से संपर्क करें।",
              )}
            </p>
          </section>
        ) : (
          <form
            className="form-card login-form"
            noValidate
            onSubmit={handleSubmit(submit)}
          >
            {(worker || supervisor) && (
              <FormField
                id="login-organization"
                label={t("Organization ID", "संगठन आईडी")}
                autoComplete="organization"
                placeholder="ORG-XXXX"
                required
                {...register("organizationId")}
                error={errors.organizationId?.message}
              />
            )}
            {worker ? (
              <>
                <FormField
                  id="employee-id"
                  label={t("Employee ID", "कर्मचारी आईडी")}
                  autoComplete="username"
                  placeholder={t("Your Employee ID", "आपकी कर्मचारी आईडी")}
                  required
                  {...register("employeeId")}
                  error={errors.employeeId?.message}
                />
                <FormField
                  id="worker-pin"
                  label={t("6-digit PIN", "6 अंकों का पिन")}
                  type="password"
                  inputMode="numeric"
                  maxLength={6}
                  autoComplete="current-password"
                  placeholder="••••••"
                  required
                  {...register("pin")}
                  error={errors.pin?.message}
                />
              </>
            ) : (
              <>
                <FormField
                  id="login-email"
                  label={
                    supervisor
                      ? t("Email address", "ईमेल पता")
                      : t("Official organization email", "आधिकारिक संगठन ईमेल")
                  }
                  type="email"
                  autoComplete="username"
                  placeholder="you@organization.com"
                  required
                  {...register("email")}
                  error={errors.email?.message}
                />
                <FormField
                  id="login-password"
                  label={t("Password", "पासवर्ड")}
                  type="password"
                  autoComplete="current-password"
                  required
                  {...register("password")}
                  error={errors.password?.message}
                />
              </>
            )}
            <Link to={`/recover/${role}`} className="forgot-link">
              {worker
                ? t("Forgot your PIN?", "पिन भूल गए?")
                : t("Forgot your password?", "पासवर्ड भूल गए?")}
            </Link>
            {error && (
              <div className="form-alert" role="alert">
                <CircleAlert size={19} />
                <p>{error}</p>
              </div>
            )}
            <button
              type="submit"
              className="button button-primary form-submit"
              disabled={isSubmitting}
            >
              {isSubmitting && <LoaderCircle className="spin" size={18} />}
              {isSubmitting
                ? t("Signing in…", "साइन इन हो रहा है…")
                : t("Sign in", "साइन इन")}
            </button>
            <p className="form-reassurance">
              <ShieldCheck size={15} />
              {worker
                ? t(
                    "Using a shared device? Sign out when you finish.",
                    "साझा डिवाइस है? काम पूरा होने पर साइन आउट करें।",
                  )
                : t(
                    "Your organization’s private workspace.",
                    "आपके संगठन का निजी कार्यस्थल।",
                  )}
            </p>
          </form>
        )}
        <p className="auth-switch">
          {worker || supervisor ? (
            t(
              "New to the team? Ask your supervisor or admin for access.",
              "टीम में नए हैं? प्रवेश के लिए अपने पर्यवेक्षक या प्रशासक से संपर्क करें।",
            )
          ) : (
            <>
              {t("New to ShiftProof?", "ShiftProof पर नए हैं?")}{" "}
              <Link to="/signup">
                {t("Create an organization", "एक संगठन बनाएँ")}
              </Link>
            </>
          )}
        </p>
      </main>
    </div>
  );
}
