import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Bell, Check } from "lucide-react";
import {
  ActionButton,
  Empty,
  ErrorNotice,
  FieldsForm,
  PageTitle,
  Panel,
  Status,
  When,
  formatDate,
  useWords,
} from "../../components/workspace/UI";
import { api, post, put, remove, search } from "../../lib/api";
import { useSession } from "../../lib/session";
import { usePreferences } from "../../lib/preferences";
import type { Job, Notification } from "../../lib/types";
import { useCatalog } from "../../components/workspace/Workspace";
import { OrganizationProfile } from "./Administration";

export function NotificationsPage() {
  const { t } = usePreferences();
  const w = useWords();
  const session = useSession((state) => state.session)!;
  const [unread, setUnread] = useState(false);
  const data = useQuery({
    queryKey: ["notifications", unread],
    queryFn: () =>
      api<{ items: Notification[]; unread: number }>(
        `/notifications${search({ unread })}`,
      ),
  });
  return (
    <>
      <PageTitle
        title="Notifications"
        description={t(
          "Reading a notification does not acknowledge or resolve its operational item.",
          "सूचना पढ़ने से संबंधित कार्य की प्राप्ति या समस्या समाधान की पुष्टि नहीं होती।",
        )}
      />
      <label className="check-field section-actions">
        <input
          type="checkbox"
          checked={unread}
          onChange={(event) => setUnread(event.target.checked)}
        />
        {t("Unread only", "केवल अपठित")}
      </label>
      <Panel>
        <When loading={data.isLoading} error={data.error}>
          {!data.data?.items.length ? (
            <Empty />
          ) : (
            data.data.items.map((item) => (
              <article
                className={`notification-row ${item.read_at ? "" : "notification-unread"}`}
                key={item.id}
              >
                <Bell size={20} />
                <div>
                  <Link to={item.href}>
                    <h3>{item.title}</h3>
                    <p>{item.body}</p>
                  </Link>
                  <small>
                    {formatDate(item.created_at, session.organization.timezone)}
                  </small>
                </div>
                {!item.read_at && (
                  <ActionButton
                    action={() => post(`/notifications/${item.id}/read`)}
                  >
                    <Check size={15} />
                    {w("Mark as read")}
                  </ActionButton>
                )}
              </article>
            ))
          )}
        </When>
      </Panel>
    </>
  );
}

type DeviceSession = {
  id: string;
  device: string;
  created_at: string;
  last_seen: string;
  expires_at: string;
  current: boolean;
};
export function SettingsPage() {
  const { departments, teams, shifts } = useCatalog();
  const assignments = useQuery({
    queryKey: ["shift-assignments"],
    queryFn: () =>
      api<{ user_id: string; shift_id: string; active: boolean }[]>(
        "/shift-assignments",
      ),
  });
  const session = useSession((state) => state.session)!;
  const { t, theme, language, toggleLanguage } = usePreferences();
  const w = useWords();
  const [error, setError] = useState<unknown>(null);
  const sessions = useQuery({
    queryKey: ["sessions"],
    queryFn: () => api<DeviceSession[]>("/auth/sessions"),
  });
  const queue = useQuery({
    queryKey: ["operations-queue"],
    queryFn: () => api<Job[]>("/operations/queue"),
    enabled: session.user.role === "organization",
  });
  return (
    <>
      <PageTitle
        title="Settings"
        description={t(
          "Your preferences, account security, and workspace configuration.",
          "आपकी प्राथमिकताएँ, खाते की सुरक्षा और कार्यस्थल सेटअप।",
        )}
      />
      <div className="work-two-column">
        <Panel title={t("Personal preferences", "व्यक्तिगत प्राथमिकताएँ")}>
          <FieldsForm
            fields={[
              {
                name: "language",
                label: t("Interface language", "इंटरफ़ेस की भाषा"),
                type: "select",
                required: true,
                defaultValue: language,
                options: [
                  { value: "en", label: "English" },
                  { value: "hi", label: "हिन्दी" },
                ],
              },
              {
                name: "speech_language",
                label: "Speech language",
                type: "select",
                required: true,
                defaultValue:
                  session.user.preferences.speech_language || "hi-IN,en-IN",
                options: [
                  { value: "hi-IN,en-IN", label: "हिन्दी / Hinglish" },
                  { value: "hi-IN", label: "हिन्दी" },
                  { value: "en-IN", label: "English" },
                ],
              },
              {
                name: "desktop",
                label: t(
                  "Desktop notifications while the workspace is open",
                  "कार्यस्थल खुला होने पर डेस्कटॉप सूचनाएँ",
                ),
                type: "checkbox",
                defaultValue: !!session.user.preferences.notifications?.desktop,
              },
            ]}
            onSubmit={async (values) => {
              const result = await put("/auth/preferences", {
                theme,
                language: values.language,
                speech_language: values.speech_language,
                notifications: { desktop: !!values.desktop },
              });
              if (values.language !== language) toggleLanguage();
              if (
                values.desktop &&
                "Notification" in window &&
                Notification.permission === "default"
              )
                await Notification.requestPermission();
              return result;
            }}
          >
            <p className="field-hint">
              {t(
                "Critical events remain in the notification inbox. Speech language is independent of interface language.",
                "गंभीर घटनाएँ सूचना इनबॉक्स में रहती हैं। बोलने की भाषा इंटरफ़ेस की भाषा से अलग है।",
              )}
            </p>
          </FieldsForm>
        </Panel>
        <Panel title={t("Change password or PIN", "पासवर्ड या पिन बदलें")}>
          <FieldsForm
            fields={[
              {
                name: "current",
                label: "Current password or PIN",
                type: "password",
                required: true,
              },
              {
                name: "replacement",
                label: "New password or PIN",
                type: "password",
                required: true,
              },
              {
                name: "confirm",
                label: "Confirm",
                type: "password",
                required: true,
              },
            ]}
            onSubmit={(values) => put("/auth/password", values)}
          >
            <p className="field-hint">
              {session.user.role === "worker"
                ? t(
                    "Choose exactly six digits. Other sessions are revoked after a change.",
                    "ठीक छह अंक चुनें। बदलाव के बाद अन्य सत्र बंद हो जाते हैं।",
                  )
                : t(
                    "Use at least 12 characters with a letter and a number. Other sessions are revoked.",
                    "कम से कम 12 अक्षर और एक अंक रखें। अन्य सत्र बंद हो जाएँगे।",
                  )}
            </p>
          </FieldsForm>
        </Panel>
      </div>
      <Panel title={t("Your profile", "आपकी प्रोफ़ाइल")}>
        <dl className="work-definition">
          <div>
            <dt>{w("Organization")}</dt>
            <dd>{session.organization.name}</dd>
          </div>
          <div>
            <dt>{w("Status")}</dt>
            <dd>
              <Status value={session.user.active ? "Active" : "Inactive"} />
            </dd>
          </div>
          {session.user.role !== "worker" && (
            <div>
              <dt>{t("Account identity", "खाते की पहचान")}</dt>
              <dd>
                {session.user.email}
                <br />
                {session.user.id}
              </dd>
            </div>
          )}
          <div>
            <dt>{w("Departments")}</dt>
            <dd>
              {session.memberships
                .filter((m) => m.active)
                .map(
                  (m) =>
                    `${departments.data?.find((d) => d.id === m.department_id)?.name || ""}${m.primary ? ` (${w("Primary")})` : m.backup ? ` (${w("Backup")})` : ""}`,
                )
                .join(" · ") || "—"}
            </dd>
          </div>
          <div>
            <dt>{w("Teams")}</dt>
            <dd>
              {session.teamMemberships
                .filter((m) => m.active)
                .map(
                  (m) =>
                    teams.data?.find((team) => team.id === m.team_id)?.name,
                )
                .join(" · ") || "—"}
            </dd>
          </div>
          <div>
            <dt>{w("Shifts")}</dt>
            <dd>
              {assignments.data
                ?.filter((a) => a.active && a.user_id === session.user.id)
                .map((a) => shifts.data?.find((s) => s.id === a.shift_id)?.name)
                .join(" · ") || "—"}
            </dd>
          </div>
        </dl>
        {session.user.role === "supervisor" && (
          <div className="work-note">
            {session.memberships
              .filter((m) => m.active)
              .map((m) => (
                <p key={m.department_id}>
                  {
                    departments.data?.find((d) => d.id === m.department_id)
                      ?.name
                  }
                  : {m.permissions.map(w).join(" · ")}
                </p>
              ))}
          </div>
        )}

        {session.user.role === "worker" ? (
          <>
            <dl className="work-definition">
              <div>
                <dt>{w("Full name")}</dt>
                <dd>{session.user.name}</dd>
              </div>
              <div>
                <dt>{w("Employee ID")}</dt>
                <dd>{session.user.employee_code}</dd>
              </div>
              <div>
                <dt>{w("Organization ID")}</dt>
                <dd>{session.organization.code}</dd>
              </div>
            </dl>
            <p className="work-note">
              {t(
                "Ask your supervisor to update your workforce identity or assignments.",
                "कर्मचारी की पहचान या जिम्मेदारी बदलने के लिए पर्यवेक्षक से संपर्क करें।",
              )}
            </p>
          </>
        ) : (
          <FieldsForm
            fields={[
              {
                name: "name",
                label: "Full name",
                required: true,
                defaultValue: session.user.name,
              },
              {
                name: "phone",
                label: "Contact number",
                defaultValue: session.user.phone,
              },
            ]}
            onSubmit={(values) => put("/profile", values)}
          />
        )}
      </Panel>
      <Panel title={t("Signed-in devices", "साइन इन किए डिवाइस")}>
        <When loading={sessions.isLoading} error={sessions.error}>
          {sessions.data?.map((device) => (
            <div className="work-list-row" key={device.id}>
              <div>
                <strong>
                  {device.current
                    ? t("This device", "यह डिवाइस")
                    : t("Another device", "अन्य डिवाइस")}
                </strong>
                <p className="device-name">{device.device}</p>
                <small>
                  {t("Last active", "अंतिम गतिविधि")}:{" "}
                  {formatDate(device.last_seen, session.organization.timezone)}
                </small>
              </div>
              {!device.current && (
                <ActionButton
                  action={() => remove(`/auth/sessions/${device.id}`)}
                >
                  {t("Revoke session", "सत्र बंद करें")}
                </ActionButton>
              )}
            </div>
          ))}
        </When>
      </Panel>
      {session.user.role === "organization" && (
        <>
          <Panel title={t("Organization profile", "संगठन प्रोफ़ाइल")}>
            <OrganizationProfile />
            <div className="logo-upload">
              <label className="form-field">
                {t("Organization logo", "संगठन का लोगो")}
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  onChange={async (event) => {
                    const file = event.target.files?.[0];
                    if (!file) return;
                    setError(null);
                    try {
                      const body = new FormData();
                      body.set("file", file);
                      body.set("kind", "logo");
                      const asset = await api<{ id: string }>("/files", {
                        method: "POST",
                        body,
                      });
                      await put("/organization", {
                        name: session.organization.name,
                        industry: session.organization.industry,
                        contact: session.organization.contact,
                        timezone: session.organization.timezone,
                        contact_email:
                          session.organization.settings.contact_email,
                        address: session.organization.settings.address || "",
                        logo_asset_id: asset.id,
                      });
                      window.location.reload();
                    } catch (cause) {
                      setError(cause);
                    }
                  }}
                />
              </label>
              {!!error && <ErrorNotice error={error} />}
            </div>
          </Panel>
          <Panel
            title={t(
              "Processing and delivery status",
              "प्रक्रिया और वितरण स्थिति",
            )}
          >
            <When loading={queue.isLoading} error={queue.error}>
              {!queue.data?.length ? (
                <Empty />
              ) : (
                queue.data.map((job) => (
                  <div className="work-list-row" key={job.id}>
                    <div>
                      <strong>{job.kind}</strong>
                      <small>
                        {formatDate(
                          job.created_at,
                          session.organization.timezone,
                        )}
                      </small>
                      {job.error && <p className="field-error">{job.error}</p>}
                    </div>
                    <Status value={job.status} />
                  </div>
                ))
              )}
            </When>
          </Panel>
        </>
      )}
    </>
  );
}

type AuditEvent = {
  id: string;
  actor_id: string | null;
  actor_role: string;
  action: string;
  entity_type: string;
  entity_id: string;
  created_at: string;
  before: Record<string, unknown>;
  after: Record<string, unknown>;
  purpose: string;
  redacted?: boolean;
};
export function AuditPage() {
  const session = useSession((state) => state.session)!;
  const { t } = usePreferences();
  const w = useWords();
  const [action, setAction] = useState("");
  const [type, setType] = useState("");
  const [page, setPage] = useState(1);
  const data = useQuery({
    queryKey: ["audit", action, type, page],
    queryFn: () =>
      api<{ items: AuditEvent[]; total: number }>(
        `/audit${search({ action, entity_type: type, page, limit: 30 })}`,
      ),
  });
  const readable = (value: unknown): string =>
    Array.isArray(value)
      ? value.map(readable).join(", ")
      : value && typeof value === "object"
        ? Object.entries(value)
            .map(
              ([key, value]) =>
                `${key.replaceAll("_", " ")}: ${readable(value)}`,
            )
            .join("; ")
        : String(value ?? "—");
  return (
    <>
      <PageTitle
        title="Audit history"
        description={t(
          "Attributable actions, policy changes and sensitive access. Records are append-only.",
          "दर्ज कार्रवाइयाँ, नीति बदलाव और संवेदनशील पहुँच। पुराने रिकॉर्ड बदले नहीं जाते।",
        )}
      />
      <div className="work-filters">
        <label>
          {t("Action contains", "कार्रवाई में शब्द")}
          <input
            value={action}
            onChange={(event) => {
              setAction(event.target.value);
              setPage(1);
            }}
          />
        </label>
        <label>
          {t("Record type", "रिकॉर्ड का प्रकार")}
          <select
            value={type}
            onChange={(event) => {
              setType(event.target.value);
              setPage(1);
            }}
          >
            <option value="">{w("All")}</option>
            {[
              "organization",
              "department",
              "team",
              "shift",
              "user",
              "task",
              "report",
              "alert",
              "conflict",
              "handover",
              "file_asset",
              "policy",
              "takeover",
            ].map((value) => (
              <option key={value} value={value}>
                {value.replaceAll("_", " ")}
              </option>
            ))}
          </select>
        </label>
      </div>
      <Panel>
        <When loading={data.isLoading} error={data.error}>
          {!data.data?.items.length ? (
            <Empty />
          ) : (
            data.data.items.map((event) => (
              <details className="audit-event" key={event.id}>
                <summary>
                  <span>
                    <strong>{event.action.replaceAll(".", " · ")}</strong>
                    <small>
                      {event.actor_role} ·{" "}
                      {formatDate(
                        event.created_at,
                        session.organization.timezone,
                      )}
                    </small>
                  </span>
                  <span>{event.entity_type}</span>
                </summary>
                <dl className="work-definition">
                  <div>
                    <dt>{t("Actor", "कार्रवाई करने वाला")}</dt>
                    <dd>{event.actor_id || t("System", "सिस्टम")}</dd>
                  </div>
                  <div>
                    <dt>{t("Record", "रिकॉर्ड")}</dt>
                    <dd>{event.entity_id}</dd>
                  </div>
                </dl>
                {event.redacted ? (
                  <p className="work-note">
                    {t(
                      "Sensitive operational details are restricted by privacy policy.",
                      "संवेदनशील संचालन विवरण गोपनीयता नीति से सीमित हैं।",
                    )}
                  </p>
                ) : (
                  <>
                    {event.purpose && (
                      <p className="work-copy">{event.purpose}</p>
                    )}
                    {Object.keys(event.before).length > 0 && (
                      <p className="audit-change">
                        <strong>{t("Before", "पहले")}: </strong>
                        {readable(event.before)}
                      </p>
                    )}
                    {Object.keys(event.after).length > 0 && (
                      <p className="audit-change">
                        <strong>{t("After", "बाद में")}: </strong>
                        {readable(event.after)}
                      </p>
                    )}
                  </>
                )}
              </details>
            ))
          )}
        </When>
      </Panel>
      <div className="pagination">
        <button
          className="button button-outline"
          disabled={page === 1}
          onClick={() => setPage(page - 1)}
        >
          {w("Previous page")}
        </button>
        <span>
          {page} / {Math.max(1, Math.ceil((data.data?.total || 0) / 30))}
        </span>
        <button
          className="button button-outline"
          disabled={page * 30 >= (data.data?.total || 0)}
          onClick={() => setPage(page + 1)}
        >
          {w("Next page")}
        </button>
      </div>
    </>
  );
}
