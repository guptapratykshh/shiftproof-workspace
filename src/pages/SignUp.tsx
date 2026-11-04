import { useState } from "react";
import { Link } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  ArrowLeft,
  Check,
  CircleAlert,
  LoaderCircle,
  Mail,
} from "lucide-react";
import { Header } from "../components/Header";
import { FormField } from "../components/FormField";
import { industries } from "../lib/industries";
import { usePreferences } from "../lib/preferences";
import { authErrorMessage, requestAuth, type AuthResult } from "../lib/auth";

type SignupValues = {
  fullName: string;
  organizationName: string;
  email: string;
  organizationType: string;
  phone: string;
  password: string;
  confirmPassword: string;
};

export function SignUp() {
  const { t } = usePreferences();
  const [error, setError] = useState("");
  const [registration, setRegistration] = useState<AuthResult | null>(null);
  const schema = z
    .object({
      fullName: z
        .string()
        .trim()
        .min(2, t("Enter your full name.", "अपना पूरा नाम भरें।")),
      organizationName: z
        .string()
        .trim()
        .min(
          2,
          t("Enter your organization’s name.", "अपने संगठन का नाम भरें।"),
        ),
      email: z.email(
        t("Enter a valid organization email.", "एक मान्य संगठन ईमेल भरें।"),
      ),
      organizationType: z
        .string()
        .refine(
          (value) => industries.some((item) => item.id === value),
          t("Choose an organization type.", "संगठन का प्रकार चुनें।"),
        ),
      phone: z
        .string()
        .trim()
        .refine(
          (value) => !value || /^[+\d()\s-]{7,20}$/.test(value),
          t("Enter a valid contact number.", "एक मान्य संपर्क नंबर भरें।"),
        ),
      password: z
        .string()
        .min(
          12,
          t("Use at least 12 characters.", "कम से कम 12 अक्षर इस्तेमाल करें।"),
        )
        .regex(
          /[a-zA-Z]/,
          t(
            "Include at least one letter.",
            "कम से कम एक अंग्रेज़ी अक्षर जोड़ें।",
          ),
        )
        .regex(
          /\d/,
          t("Include at least one number.", "कम से कम एक अंक जोड़ें।"),
        ),
      confirmPassword: z
        .string()
        .min(1, t("Confirm your password.", "अपने पासवर्ड की पुष्टि करें।")),
    })
    .refine((values) => values.password === values.confirmPassword, {
      path: ["confirmPassword"],
      message: t("Passwords don’t match.", "पासवर्ड मेल नहीं खाते।"),
    });
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    resetField,
  } = useForm<SignupValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      fullName: "",
      organizationName: "",
      email: "",
      organizationType: "",
      phone: "",
      password: "",
      confirmPassword: "",
    },
  });

  const submit = async (values: SignupValues) => {
    setError("");
    try {
      const { confirmPassword: _confirm, ...payload } = values;
      const result = await requestAuth("register", payload);
      resetField("password");
      resetField("confirmPassword");
      setRegistration(result);
    } catch (cause) {
      setError(authErrorMessage(cause, t));
    }
  };

  return (
    <div className="auth-page">
      <Header />
      <main id="main-content" className="signup-main">
        <div className="form-intro">
          <p className="auth-eyebrow">
            {t("The next shift starts here", "अगली शिफ्ट यहीं से शुरू होती है")}
          </p>
          <h1>{t("Create your organization.", "अपना संगठन बनाएँ।")}</h1>
          <p className="page-description">
            {t(
              "A shared workspace. A clearer handover.",
              "साझा कार्यस्थल। स्पष्ट हैंडओवर।",
            )}
          </p>
        </div>
        {registration ? (
          <section className="form-card success-card" role="status">
            <div className="role-icon">
              <Mail />
            </div>
            <h2>
              {registration.delivery === "local_outbox"
                ? t("Verification prepared locally", "सत्यापन स्थानीय रूप से तैयार है")
                : registration.delivery === "smtp_queued"
                  ? t("Verification email queued", "सत्यापन ईमेल भेजने की कतार में है")
                  : t("Verification requested", "सत्यापन का अनुरोध प्राप्त हुआ")}
            </h2>
            <p>
              {registration.delivery === "local_outbox"
                ? t(
                    "Email delivery is in local development mode. No email will arrive in your inbox. Open the latest verification message in backend/data/outbox and follow its link to continue.",
                    "ईमेल अभी स्थानीय विकास मोड में है। आपके इनबॉक्स में ईमेल नहीं आएगा। backend/data/outbox में नवीनतम सत्यापन संदेश खोलें और उसके लिंक से आगे बढ़ें।",
                  )
                : registration.delivery === "smtp_queued"
                  ? t(
                      "Your verification email is queued for delivery. Check your inbox and spam folder shortly, then follow the link to continue setting up your workspace.",
                      "आपका सत्यापन ईमेल भेजने की कतार में है। थोड़ी देर में इनबॉक्स और स्पैम फ़ोल्डर जाँचें, फिर कार्यस्थल का सेटअप जारी रखने के लिए लिंक खोलें।",
                    )
                  : t(
                      "Your registration requires email verification. Contact the workspace administrator if you do not receive a verification link.",
                      "पंजीकरण के लिए ईमेल सत्यापन ज़रूरी है। सत्यापन लिंक न मिलने पर कार्यस्थल प्रशासक से संपर्क करें।",
                    )}
            </p>
            <Link className="button button-primary" to="/signin/organization">
              {t("Back to sign in", "साइन इन पर वापस जाएँ")}
            </Link>
          </section>
        ) : (
          <form
            className="form-card signup-form"
            noValidate
            onSubmit={handleSubmit(submit)}
          >
            <div className="form-card-heading">
              <h2>
                {t("Your organization, connected.", "आपका संगठन, एक साथ।")}
              </h2>
              <p>
                {t(
                  "Start with your details. You can set up your team next.",
                  "पहले अपना विवरण भरें। इसके बाद अपनी टीम सेट करें।",
                )}
              </p>
            </div>
            <div className="form-grid">
              <FormField
                id="full-name"
                label={t("Full name", "पूरा नाम")}
                autoComplete="name"
                placeholder={t("Your full name", "आपका पूरा नाम")}
                required
                {...register("fullName")}
                error={errors.fullName?.message}
              />
              <FormField
                id="organization-name"
                label={t("Organization name", "संगठन का नाम")}
                autoComplete="organization"
                placeholder={t("Your organization", "आपका संगठन")}
                required
                {...register("organizationName")}
                error={errors.organizationName?.message}
              />
              <FormField
                id="signup-email"
                wide
                label={t("Official organization email", "आधिकारिक संगठन ईमेल")}
                type="email"
                autoComplete="email"
                placeholder="you@organization.com"
                required
                {...register("email")}
                error={errors.email?.message}
              />
              <div className="form-field">
                <label htmlFor="organization-type">
                  {t("Organization type", "संगठन का प्रकार")}
                </label>
                <select
                  id="organization-type"
                  required
                  aria-invalid={!!errors.organizationType}
                  aria-describedby={
                    errors.organizationType
                      ? "organization-type-error"
                      : undefined
                  }
                  {...register("organizationType")}
                >
                  <option value="">
                    {t("Select your industry", "अपना उद्योग चुनें")}
                  </option>
                  {industries.map((industry) => (
                    <option key={industry.id} value={industry.id}>
                      {t(industry.name, industry.hi)}
                    </option>
                  ))}
                </select>
                {errors.organizationType && (
                  <p className="field-error" id="organization-type-error">
                    {errors.organizationType.message}
                  </p>
                )}
              </div>
              <FormField
                id="phone"
                label={t("Contact number (optional)", "संपर्क नंबर (वैकल्पिक)")}
                type="tel"
                autoComplete="tel"
                placeholder="+91"
                {...register("phone")}
                error={errors.phone?.message}
              />
              <FormField
                id="signup-password"
                label={t("Password", "पासवर्ड")}
                type="password"
                autoComplete="new-password"
                placeholder={t("Create a password", "पासवर्ड बनाएँ")}
                required
                {...register("password")}
                error={errors.password?.message}
                hint={t(
                  "12+ characters, including a letter and a number.",
                  "12+ अक्षर, एक अंग्रेज़ी अक्षर और एक अंक सहित।",
                )}
              />
              <FormField
                id="confirm-password"
                label={t("Confirm password", "पासवर्ड की पुष्टि")}
                type="password"
                autoComplete="new-password"
                placeholder={t("Re-enter your password", "पासवर्ड फिर से भरें")}
                required
                {...register("confirmPassword")}
                error={errors.confirmPassword?.message}
              />
            </div>
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
                ? t("Creating your account…", "खाता बनाया जा रहा है…")
                : t("Create account", "खाता बनाएँ")}
            </button>
            <p className="form-reassurance">
              <Check size={15} />
              {t(
                "Verify your email before your workspace is created.",
                "कार्यस्थल बनने से पहले ईमेल सत्यापित करें।",
              )}
            </p>
          </form>
        )}
        <p className="auth-switch">
          {t("Already have an account?", "पहले से खाता है?")}{" "}
          <Link to="/signin">{t("Sign in", "साइन इन")}</Link>
        </p>
        <Link to="/" className="back-home">
          <ArrowLeft size={15} />
          {t("Back to ShiftProof", "ShiftProof पर वापस जाएँ")}
        </Link>
      </main>
    </div>
  );
}
