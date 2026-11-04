import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useLocation } from "react-router-dom";
import { Header } from "../components/Header";
import {
  ActionButton,
  ErrorNotice,
  FieldsForm,
  Loading,
} from "../components/workspace/UI";
import { api, post, search } from "../lib/api";
import { usePreferences } from "../lib/preferences";

export function Activation() {
  const { pathname } = useLocation();
  const verify = pathname === "/verify-email";
  const { t } = usePreferences();
  const [token] = useState(
    () => new URLSearchParams(location.search).get("token") || "",
  );
  const [result, setResult] = useState<{
    organizationId: string;
    role?: string;
  } | null>(null);
  const info = useQuery({
    queryKey: ["activation", token],
    queryFn: () =>
      api<{ role: string; name: string; organizationId: string; kind: string }>(
        `/auth/activation${search({ token })}`,
      ),
    enabled: !verify && !!token && !result,
    retry: false,
  });
  const worker = info.data?.role === "worker";
  return (
    <div className="auth-page">
      <Header />
      <main id="main-content" className="login-main">
        <div className="form-intro">
          <p className="auth-eyebrow">
            {t("Your private workspace", "आपका निजी कार्यस्थल")}
          </p>
          <h1>
            {verify
              ? t("Verify your email.", "अपना ईमेल सत्यापित करें।")
              : t("Make this account yours.", "अपना खाता तैयार करें।")}
          </h1>
          <p className="page-description">
            {verify
              ? t(
                  "Confirm your official email to create your organization.",
                  "अपना संगठन बनाने के लिए आधिकारिक ईमेल की पुष्टि करें।",
                )
              : t(
                  "Choose your own password or PIN. Never share it with anyone.",
                  "अपना पासवर्ड या पिन चुनें। इसे किसी से साझा न करें।",
                )}
          </p>
        </div>
        <section className="form-card">
          {!token ? (
            <ErrorNotice
              error={t(
                "This link is incomplete. Open the full link from your invitation.",
                "यह लिंक अधूरा है। आमंत्रण का पूरा लिंक खोलें।",
              )}
            />
          ) : result ? (
            <div className="success-card">
              <h2>{t("Your account is ready.", "आपका खाता तैयार है।")}</h2>
              <p>
                {t("Organization ID", "संगठन आईडी")}:{" "}
                <strong>{result.organizationId}</strong>
              </p>
              <Link
                className="button button-primary"
                to={`/signin/${result.role || "organization"}`}
              >
                {t("Continue to sign in", "साइन इन करें")}
              </Link>
            </div>
          ) : verify ? (
            <ActionButton
              className="button button-primary"
              action={async () => {
                const response = await post<{ organizationId: string }>(
                  "/auth/verify",
                  { token },
                );
                setResult(response);
                history.replaceState(null, "", pathname);
              }}
            >
              {t(
                "Verify email and create organization",
                "ईमेल सत्यापित करके संगठन बनाएँ",
              )}
            </ActionButton>
          ) : info.isLoading ? (
            <Loading />
          ) : info.error ? (
            <ErrorNotice error={info.error} />
          ) : (
            <>
              <p className="work-note">
                {info.data?.name} · {info.data?.organizationId}
              </p>
              <FieldsForm
                fields={[
                  {
                    name: "secret",
                    label: worker ? "PIN" : "Password",
                    type: "password",
                    required: true,
                    hint: worker
                      ? t("Exactly six digits.", "ठीक छह अंक।")
                      : t(
                          "At least 12 characters, including a letter and number.",
                          "कम से कम 12 अक्षर, जिनमें एक अक्षर और अंक हो।",
                        ),
                  },
                  {
                    name: "confirm",
                    label: worker ? "Confirm PIN" : "Confirm password",
                    type: "password",
                    required: true,
                  },
                ]}
                submitLabel="Continue"
                onSubmit={async (values) => {
                  const response = await post<{
                    organizationId: string;
                    role: string;
                  }>("/auth/activate", {
                    token,
                    [worker ? "pin" : "password"]: values.secret,
                    confirm: values.confirm,
                  });
                  setResult(response);
                  history.replaceState(null, "", pathname);
                }}
              />
            </>
          )}
        </section>
      </main>
    </div>
  );
}
