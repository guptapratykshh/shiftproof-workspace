export type AuthAction = "register" | "login" | "recover";
export type AuthRole = "worker" | "supervisor" | "organization";
export type AuthResult = {
  status: "verification_required" | "authenticated" | "recovery_requested";
  redirectPath?: string;
  delivery?: "local_outbox" | "smtp_queued";
};

export class AuthRequestError extends Error {
  constructor(
    public reason: "unavailable" | "network" | "rejected" | "invalid-response",
    public status = 0,
  ) {
    super(reason);
    this.name = "AuthRequestError";
  }
}

/** Integration boundary only. Authentication requires a separately configured API. */
export async function requestAuth(
  action: AuthAction,
  payload: Record<string, string>,
  role?: AuthRole,
): Promise<AuthResult> {
  const base = import.meta.env.VITE_API_BASE_URL?.trim().replace(/\/$/, "");
  if (!base) throw new AuthRequestError("unavailable");
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 15_000);
  try {
    const response = await fetch(
      `${base}/auth/${action}${action === "login" ? `/${role}` : ""}`,
      {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: controller.signal,
      },
    );
    if (!response.ok) throw new AuthRequestError("rejected", response.status);
    const result: unknown = await response.json();
    const expected = {
      register: "verification_required",
      login: "authenticated",
      recover: "recovery_requested",
    }[action];
    if (
      typeof result !== "object" ||
      result === null ||
      !("status" in result) ||
      result.status !== expected
    )
      throw new AuthRequestError("invalid-response");
    return {
      status: expected as AuthResult["status"],
      delivery:
        "delivery" in result &&
        (result.delivery === "local_outbox" || result.delivery === "smtp_queued")
          ? result.delivery
          : undefined,
      redirectPath:
        "redirectPath" in result && typeof result.redirectPath === "string"
          ? result.redirectPath
          : undefined,
    };
  } catch (error) {
    if (error instanceof AuthRequestError) throw error;
    throw new AuthRequestError("network");
  } finally {
    window.clearTimeout(timeout);
  }
}

export function authErrorMessage(
  error: unknown,
  t: (english: string, hindi: string) => string,
): string {
  if (error instanceof AuthRequestError) {
    if (error.reason === "unavailable")
      return t(
        "Account access is not available yet. Please try again when your organization’s workspace is connected. Your details have not been submitted.",
        "खाता सेवा अभी उपलब्ध नहीं है। संगठन का कार्यस्थल जुड़ने के बाद फिर कोशिश करें। आपका विवरण भेजा नहीं गया है।",
      );
    if (error.status === 401 || error.status === 403)
      return t(
        "We couldn’t sign you in with those details. Check your information and try again.",
        "इस जानकारी से साइन इन नहीं हुआ। अपना विवरण जाँचें और फिर कोशिश करें।",
      );
    if (error.status === 429)
      return t(
        "Too many attempts. Please wait a little before trying again.",
        "बहुत अधिक प्रयास हुए हैं। थोड़ा इंतज़ार करके फिर कोशिश करें।",
      );
    if (error.status === 409)
      return t(
        "An account may already use these details. Try signing in or recovering your account.",
        "इस जानकारी से खाता पहले से हो सकता है। साइन इन या खाता रिकवरी का प्रयास करें।",
      );
  }
  return t(
    "We couldn’t complete your request. Check your connection and try again. Your entries are still here.",
    "अनुरोध पूरा नहीं हुआ। कनेक्शन जाँचकर फिर कोशिश करें। भरी हुई जानकारी यहीं है।",
  );
}
