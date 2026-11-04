export const API_BASE =
  import.meta.env.VITE_API_BASE_URL?.trim().replace(/\/$/, "") || "";
let accountId: string | null = null;
let lastUserActivity = Date.now();
const activity = () => {
  lastUserActivity = Date.now();
};
window.addEventListener("pointerdown", activity, { passive: true });
window.addEventListener("keydown", activity);
export function setAccountId(value: string | null) {
  accountId = value;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status = 0,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  if (!API_BASE)
    throw new ApiError(
      "The workspace service is not connected. Configure the API address to use operational features.",
      503,
    );
  const csrf = document.cookie
    .split("; ")
    .find((cookie) => cookie.startsWith("shiftproof_csrf="))
    ?.split("=")[1];
  const headers = new Headers(options.headers);
  headers.set(
    "X-User-Activity",
    Date.now() - lastUserActivity < 60_000 ? "1" : "0",
  );
  if (options.body && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  if (csrf) headers.set("X-CSRF-Token", decodeURIComponent(csrf));
  if (accountId && !headers.has("X-Account-ID"))
    headers.set("X-Account-ID", accountId);
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
      credentials: "include",
      signal: options.signal || AbortSignal.timeout(30_000),
    });
  } catch {
    throw new ApiError(
      "The connection was interrupted. Your unsent information is still here.",
    );
  }
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json"))
    throw new ApiError(
      "The workspace service is unavailable. Please try again later.",
      503,
    );
  const result = await response.json();
  if (!response.ok) {
    if (response.status === 401)
      window.dispatchEvent(new Event("shiftproof-session-ended"));
    const detail = result.detail;
    throw new ApiError(
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail
              .map(
                (item: { loc?: string[]; msg?: string }) =>
                  `${item.loc?.slice(1).join(" ") || "Field"}: ${item.msg || "Check this value"}`,
              )
              .join(". ")
          : "The request could not be completed.",
      response.status,
    );
  }
  return result as T;
}

export const post = <T>(path: string, value: unknown = {}) =>
  api<T>(path, { method: "POST", body: JSON.stringify(value) });
export const put = <T>(path: string, value: unknown) =>
  api<T>(path, { method: "PUT", body: JSON.stringify(value) });
export const remove = <T>(path: string) => api<T>(path, { method: "DELETE" });
export function search(
  values: Record<string, string | number | boolean | null | undefined>,
) {
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== "")
      params.set(key, String(value));
  });
  return params.size ? `?${params}` : "";
}

export async function evidenceUrl(id: string, purpose = "") {
  const response = await fetch(
    `${API_BASE}/files/${id}${search({ purpose })}`,
    {
      credentials: "include",
      headers: accountId ? { "X-Account-ID": accountId } : {},
      signal: AbortSignal.timeout(30_000),
    },
  );
  if (!response.ok) {
    const result = await response.json().catch(() => ({}));
    throw new ApiError(
      result.detail || "Evidence could not be loaded.",
      response.status,
    );
  }
  return URL.createObjectURL(await response.blob());
}
