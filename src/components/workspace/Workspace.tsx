import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, NavLink, Outlet } from "react-router-dom";
import {
  Activity,
  Bell,
  Building2,
  CalendarDays,
  ClipboardCheck,
  FileText,
  Gauge,
  GitBranch,
  Handshake,
  History,
  LayoutDashboard,
  LogOut,
  Menu,
  Mic,
  Settings,
  ShieldCheck,
  TriangleAlert,
  Users,
  WifiOff,
  X,
} from "lucide-react";
import { Header } from "../Header";
import { API_BASE, api, evidenceUrl } from "../../lib/api";
import { useSession, useSessionBootstrap, useSignOut } from "../../lib/session";
import { loadDrafts, syncDrafts } from "../../lib/offline";
import { usePreferences } from "../../lib/preferences";
import type {
  Department,
  Notification,
  Paged,
  Person,
  Shift,
  Team,
} from "../../lib/types";
import { ErrorNotice, Loading, useWords } from "./UI";

function OrganizationLogo({ id }: { id: string }) {
  const [url, setUrl] = useState("");
  useEffect(() => {
    let cancelled = false;
    let blobUrl = "";
    void evidenceUrl(id)
      .then((value) => {
        blobUrl = value;
        if (cancelled) URL.revokeObjectURL(value);
        else setUrl(value);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
      if (blobUrl) URL.revokeObjectURL(blobUrl);
    };
  }, [id]);
  return url ? <img className="organization-logo" src={url} alt="" /> : null;
}
const workerNavigation = ["", "tasks", "record", "notifications", "settings"];
const workerTitles: Record<string, string> = {
  "": "Home",
  tasks: "My tasks",
  record: "Report",
  notifications: "Notifications",
  settings: "Profile",
};
const links = [
  {
    path: "notifications",
    title: "Notifications",
    icon: Bell,
    roles: ["worker"],
  },
  {
    path: "",
    title: "Overview",
    icon: LayoutDashboard,
    roles: ["organization", "supervisor", "worker"],
  },
  {
    path: "attention",
    title: "Needs attention",
    icon: TriangleAlert,
    roles: ["supervisor"],
  },
  {
    path: "record",
    title: "New report",
    icon: Mic,
    roles: ["supervisor", "worker"],
  },
  {
    path: "tasks",
    title: "Tasks",
    icon: ClipboardCheck,
    roles: ["organization", "supervisor", "worker"],
  },
  {
    path: "reports",
    title: "Reports",
    icon: FileText,
    roles: ["organization", "supervisor", "worker"],
  },
  {
    path: "handovers",
    title: "Handovers",
    icon: Handshake,
    roles: ["organization", "supervisor", "worker"],
  },
  {
    path: "alerts",
    title: "Alerts",
    icon: TriangleAlert,
    roles: ["organization", "supervisor", "worker"],
  },
  {
    path: "conflicts",
    title: "Conflicts",
    icon: GitBranch,
    roles: ["organization", "supervisor"],
  },
  {
    path: "follow-ups",
    title: "Follow-ups",
    icon: Activity,
    roles: ["organization", "supervisor"],
  },
  {
    path: "departments",
    title: "Departments",
    icon: Building2,
    roles: ["organization"],
  },
  {
    path: "workforce",
    title: "Workforce",
    icon: Users,
    roles: ["organization", "supervisor"],
  },
  {
    path: "shifts",
    title: "Shifts",
    icon: CalendarDays,
    roles: ["organization", "supervisor"],
  },
  {
    path: "supervisors",
    title: "Supervisors",
    icon: ShieldCheck,
    roles: ["organization"],
  },
  {
    path: "policies",
    title: "Policies",
    icon: ShieldCheck,
    roles: ["organization"],
  },
  {
    path: "analytics",
    title: "Analytics",
    icon: Gauge,
    roles: ["organization", "supervisor"],
  },
  {
    path: "audit",
    title: "Audit history",
    icon: History,
    roles: ["organization"],
  },
  {
    path: "drafts",
    title: "Local drafts",
    icon: FileText,
    roles: ["supervisor", "worker"],
  },
  {
    path: "settings",
    title: "Settings",
    icon: Settings,
    roles: ["organization", "supervisor", "worker"],
  },
];

async function allWorkers(): Promise<Paged<Person>> {
  const result = await api<Paged<Person>>("/workers?limit=200");
  for (let page = 2; result.items.length < result.total; page++) {
    const next = await api<Paged<Person>>(`/workers?limit=200&page=${page}`);
    if (!next.items.length) break;
    result.items.push(...next.items);
  }
  return result;
}

export function useCatalog() {
  const session = useSession((state) => state.session);
  const departments = useQuery({
    queryKey: ["departments"],
    queryFn: () => api<Department[]>("/departments"),
  });
  const teams = useQuery({
    queryKey: ["teams"],
    queryFn: () => api<Team[]>("/teams"),
  });
  const shifts = useQuery({
    queryKey: ["shifts"],
    queryFn: () => api<Shift[]>("/shifts"),
  });
  const workers = useQuery({
    queryKey: ["workers", "catalog"],
    queryFn: () => allWorkers(),
  });
  const supervisors = useQuery({
    queryKey: ["supervisors"],
    queryFn: () => api<Person[]>("/supervisors"),
    enabled: session?.user.role !== "worker",
  });
  return { departments, teams, shifts, workers, supervisors };
}

export function Workspace() {
  const { session, isLoading, error, ended } = useSessionBootstrap();
  const { t } = usePreferences();
  const w = useWords();
  const client = useQueryClient();
  const [navOpen, setNavOpen] = useState(false);
  useEffect(() => {
    if (!navOpen) return;
    const dismiss = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setNavOpen(false);
        document.getElementById("workspace-navigation-toggle")?.focus();
      }
    };
    document.addEventListener("keydown", dismiss);
    return () => document.removeEventListener("keydown", dismiss);
  }, [navOpen]);
  const [online, setOnline] = useState(navigator.onLine);
  const [logoutError, setLogoutError] = useState<unknown>(null);
  const [pending, setPending] = useState(0);
  const signOut = useSignOut();
  const notifications = useQuery({
    queryKey: ["notifications"],
    queryFn: () =>
      api<{ items: Notification[]; unread: number }>("/notifications"),
    enabled: !!session && !ended,
    refetchInterval: online ? 30_000 : false,
  });
  const notified = useRef<Set<string> | null>(null);
  useEffect(() => {
    notified.current = null;
  }, [session?.user.id]);
  useEffect(() => {
    const items = notifications.data?.items;
    if (!items || !session) return;
    if (!notified.current) {
      notified.current = new Set(items.map((item) => item.id));
      return;
    }
    for (const item of items) {
      if (
        !notified.current.has(item.id) &&
        !item.read_at &&
        session.user.preferences.notifications?.desktop &&
        "Notification" in window &&
        window.Notification.permission === "granted"
      ) {
        // Keep private report text off the shared device's lock screen.
        const notice = new window.Notification("ShiftProof", {
          body: t(
            "A new update is waiting in your workspace.",
            "आपके कार्यस्थल में नया अपडेट है।",
          ),
          tag: item.id,
        });
        notice.onclick = () => {
          window.focus();
          if (useSession.getState().session?.user.id === session.user.id)
            window.location.assign(item.href);
          notice.close();
        };
        setTimeout(() => notice.close(), 10_000);
      }
      notified.current.add(item.id);
    }
  }, [
    notifications.data,
    session?.user.id,
    session?.user.preferences.notifications?.desktop,
    t,
  ]);
  useEffect(() => {
    const update = () => setOnline(navigator.onLine);
    addEventListener("online", update);
    addEventListener("offline", update);
    return () => {
      removeEventListener("online", update);
      removeEventListener("offline", update);
    };
  }, []);
  useEffect(() => {
    if (!session) return;
    const current = () =>
      useSession.getState().session?.user.id === session.user.id &&
      useSession.getState().session?.organization.id ===
        session.organization.id;
    const refresh = () => {
      if (current())
        void loadDrafts(session)
          .then((drafts) =>
            setPending(
              drafts.filter(
                (draft) =>
                  !["Submitted", "Draft", "Saved locally"].includes(
                    draft.status,
                  ),
              ).length,
            ),
          )
          .catch(() => undefined);
    };
    const synchronize = () => {
      if (current())
        void syncDrafts(session, current)
          .then(refresh)
          .catch(() => undefined);
    };
    refresh();
    synchronize();
    const timer = setInterval(synchronize, 30_000);
    addEventListener("online", synchronize);
    addEventListener("shiftproof-drafts-updated", refresh);
    return () => {
      clearInterval(timer);
      removeEventListener("online", synchronize);
      removeEventListener("shiftproof-drafts-updated", refresh);
    };
  }, [session?.user.id]);
  useEffect(() => {
    if (!session || !API_BASE || !online) return;
    const refresh = () => {
      void client.invalidateQueries(
        { predicate: (query) => query.queryKey[0] !== "session" },
        // Let slower requests finish instead of restarting them every refresh.
        { cancelRefetch: false },
      );
    };
    // Temporary public tunnels may buffer SSE; keep their workspaces current.
    if (import.meta.env.VITE_LIVE_UPDATES === "poll") {
      const timer = window.setInterval(() => {
        if (document.visibilityState === "visible") refresh();
      }, 5_000);
      return () => window.clearInterval(timer);
    }
    const stream = new EventSource(`${API_BASE}/events`, {
      withCredentials: true,
    });
    stream.addEventListener("update", refresh);
    stream.addEventListener("expired", () =>
      window.dispatchEvent(new Event("shiftproof-session-ended")),
    );
    return () => stream.close();
  }, [session?.user.id, online, client]);
  if (isLoading && !ended)
    return (
      <>
        <Header />
        <main className="login-main">
          <Loading />
        </main>
      </>
    );
  if (!session || ended)
    return (
      <>
        <Header />
        <main className="login-main">
          <h1>{t("Your workspace is private.", "आपका कार्यस्थल निजी है।")}</h1>
          <p className="work-note">
            {t(
              "Sign in to continue. Local drafts stay encrypted and belong to their original reporter.",
              "जारी रखने के लिए साइन इन करें। स्थानीय ड्राफ्ट एन्क्रिप्टेड हैं और मूल कर्मचारी के ही हैं।",
            )}
          </p>
          {!!error && <ErrorNotice error={error} />}
          <Link className="button button-primary" to="/signin">
            {t("Sign in", "साइन इन")}
          </Link>
        </main>
      </>
    );
  return (
    <div className={`workspace role-${session.user.role}`}>
      <Header />
      <div className="workspace-identity">
        <button
          id="workspace-navigation-toggle"
          className="icon-button nav-toggle"
          aria-label={t(
            "Open workspace navigation",
            "कार्यस्थल नेविगेशन खोलें",
          )}
          aria-expanded={navOpen}
          onClick={() => setNavOpen(!navOpen)}
        >
          {navOpen ? <X /> : <Menu />}
        </button>
        {typeof session.organization.settings.logo_asset_id === "string" &&
          session.organization.settings.logo_asset_id && (
            <OrganizationLogo
              id={session.organization.settings.logo_asset_id}
            />
          )}
        <div>
          <strong>{session.organization.name}</strong>
          <span>
            {session.organization.code} · {session.user.name}
          </span>
        </div>
        <Link className="notification-link" to="/workspace/notifications">
          <Bell size={19} />
          {w("Notifications")}
          {!!notifications.data?.unread && <b>{notifications.data.unread}</b>}
        </Link>
      </div>
      {!online && (
        <div className="connection-banner">
          <WifiOff size={17} />
          {t(
            "Offline. Drafts save on this device; queued reports will sync when connected.",
            "ऑफ़लाइन। ड्राफ्ट इस डिवाइस पर सहेजे जाते हैं; रिपोर्ट कनेक्शन आने पर सिंक होगी।",
          )}
        </div>
      )}
      {pending > 0 && (
        <Link className="connection-banner" to="/workspace/drafts">
          {pending}{" "}
          {t(
            "reports waiting for synchronization. Review status.",
            "रिपोर्ट सिंक की प्रतीक्षा में हैं। स्थिति देखें।",
          )}
        </Link>
      )}
      <div className="workspace-grid">
        <aside className={`workspace-nav ${navOpen ? "nav-open" : ""}`}>
          <p className="eyebrow">
            {session.user.role === "worker"
              ? t("Your shift", "आपकी शिफ्ट")
              : session.user.role === "supervisor"
                ? t("Team operations", "टीम संचालन")
                : t("Organization", "संगठन")}
          </p>
          <nav aria-label={t("Workspace navigation", "कार्यस्थल नेविगेशन")}>
            {links
              .filter(
                (link) =>
                  link.roles.includes(session.user.role) &&
                  (session.user.role !== "worker" ||
                    workerNavigation.includes(link.path)),
              )
              .sort((a, b) =>
                session.user.role === "worker"
                  ? workerNavigation.indexOf(a.path) -
                    workerNavigation.indexOf(b.path)
                  : 0,
              )
              .map(({ path, title, icon: Icon }) => (
                <NavLink
                  key={path}
                  end={path === ""}
                  to={`/workspace${path ? `/${path}` : ""}`}
                  onClick={() => setNavOpen(false)}
                >
                  <Icon size={19} />
                  {w(
                    session.user.role === "worker" ? workerTitles[path] : title,
                  )}
                </NavLink>
              ))}
          </nav>
          {session.user.role === "organization" && (
            <Link className="setup-link" to="/workspace/onboarding">
              {w("Onboarding")}
              {!session.organization.active && <StatusDot />}
            </Link>
          )}
          <button
            className="signout-button"
            onClick={() => {
              setLogoutError(null);
              void signOut().catch(setLogoutError);
            }}
          >
            <LogOut size={18} />
            {w("Sign out")}
          </button>
          {!!logoutError && <ErrorNotice error={logoutError} />}
        </aside>
        <main id="main-content" className="workspace-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
function StatusDot() {
  return <span className="setup-dot" aria-label="Pending" />;
}
