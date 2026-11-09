import React, { Suspense, lazy, useEffect } from "react";
import ReactDOM from "react-dom/client";
import {
  BrowserRouter,
  Link,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import "@fontsource/inter/latin-400.css";
import "@fontsource/inter/latin-500.css";
import "@fontsource/inter/latin-600.css";
import "@fontsource/inter/latin-700.css";
import "@fontsource/noto-sans-devanagari/devanagari-400.css";
import "@fontsource/noto-sans-devanagari/devanagari-600.css";
import { PreferencesProvider, usePreferences } from "./lib/preferences";
import { Landing } from "./pages/Landing";
import { SignIn } from "./pages/SignIn";
import { SignUp } from "./pages/SignUp";
import { RoleLogin } from "./pages/RoleLogin";
import { Recovery } from "./pages/Recovery";
import { Header } from "./components/Header";
import { AppErrorBoundary } from "./components/AppErrorBoundary";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ErrorNotice, Loading } from "./components/workspace/UI";
import { useSession } from "./lib/session";
import "./styles.css";

const TeamDetailPage = lazy(() =>
  import("./pages/workspace/Operations").then((module) => ({
    default: module.TeamDetailPage,
  })),
);
const SupervisorDetailPage = lazy(() =>
  import("./pages/workspace/Operations").then((module) => ({
    default: module.SupervisorDetailPage,
  })),
);
const AttentionPage = lazy(() =>
  import("./pages/workspace/Operations").then((module) => ({
    default: module.AttentionPage,
  })),
);
const DepartmentDetailPage = lazy(() =>
  import("./pages/workspace/Operations").then((module) => ({
    default: module.DepartmentDetailPage,
  })),
);
const Activation = lazy(() =>
  import("./pages/Activation").then((module) => ({
    default: module.Activation,
  })),
);
const Workspace = lazy(() =>
  import("./components/workspace/Workspace").then((module) => ({
    default: module.Workspace,
  })),
);
const DashboardPage = lazy(() =>
  import("./pages/workspace/Dashboard").then((module) => ({
    default: module.DashboardPage,
  })),
);
const AnalyticsPage = lazy(() =>
  import("./pages/workspace/Dashboard").then((module) => ({
    default: module.AnalyticsPage,
  })),
);
const DepartmentsPage = lazy(() =>
  import("./pages/workspace/Administration").then((module) => ({
    default: module.DepartmentsPage,
  })),
);
const OnboardingPage = lazy(() =>
  import("./pages/workspace/Administration").then((module) => ({
    default: module.OnboardingPage,
  })),
);
const PoliciesPage = lazy(() =>
  import("./pages/workspace/Administration").then((module) => ({
    default: module.PoliciesPage,
  })),
);
const ShiftsPage = lazy(() =>
  import("./pages/workspace/Administration").then((module) => ({
    default: module.ShiftsPage,
  })),
);
const SupervisorsPage = lazy(() =>
  import("./pages/workspace/Administration").then((module) => ({
    default: module.SupervisorsPage,
  })),
);
const WorkforcePage = lazy(() =>
  import("./pages/workspace/Workforce").then((module) => ({
    default: module.WorkforcePage,
  })),
);
const WorkerDetailPage = lazy(() =>
  import("./pages/workspace/Workforce").then((module) => ({
    default: module.WorkerDetailPage,
  })),
);
const TasksPage = lazy(() =>
  import("./pages/workspace/Tasks").then((module) => ({
    default: module.TasksPage,
  })),
);
const TaskDetailPage = lazy(() =>
  import("./pages/workspace/Tasks").then((module) => ({
    default: module.TaskDetailPage,
  })),
);
const ReportComposer = lazy(() =>
  import("./pages/workspace/Reporting").then((module) => ({
    default: module.ReportComposer,
  })),
);
const DraftsPage = lazy(() =>
  import("./pages/workspace/Reporting").then((module) => ({
    default: module.DraftsPage,
  })),
);
const ReportsPage = lazy(() =>
  import("./pages/workspace/Reports").then((module) => ({
    default: module.ReportsPage,
  })),
);
const ReportDetailPage = lazy(() =>
  import("./pages/workspace/Reports").then((module) => ({
    default: module.ReportDetailPage,
  })),
);
const ConflictsPage = lazy(() =>
  import("./pages/workspace/Reports").then((module) => ({
    default: module.ConflictsPage,
  })),
);
const FollowUpsPage = lazy(() =>
  import("./pages/workspace/Reports").then((module) => ({
    default: module.FollowUpsPage,
  })),
);
const AlertsPage = lazy(() =>
  import("./pages/workspace/Alerts").then((module) => ({
    default: module.AlertsPage,
  })),
);
const HandoversPage = lazy(() =>
  import("./pages/workspace/Handovers").then((module) => ({
    default: module.HandoversPage,
  })),
);
const AuditPage = lazy(() =>
  import("./pages/workspace/Account").then((module) => ({
    default: module.AuditPage,
  })),
);
const NotificationsPage = lazy(() =>
  import("./pages/workspace/Account").then((module) => ({
    default: module.NotificationsPage,
  })),
);
const SettingsPage = lazy(() =>
  import("./pages/workspace/Account").then((module) => ({
    default: module.SettingsPage,
  })),
);

function RouteEffects() {
  const { pathname } = useLocation();
  const { t } = usePreferences();
  useEffect(() => {
    window.scrollTo(0, 0);
    const title = pathname.startsWith("/workspace")
      ? t("Your workspace", "आपका कार्यस्थल")
      : pathname === "/"
        ? t(
            "The next shift starts with clarity",
            "अगली शिफ्ट की शुरुआत स्पष्टता से",
          )
        : pathname === "/signup"
          ? t("Create your organization", "अपना संगठन बनाएँ")
          : pathname.startsWith("/recover")
            ? t("Account recovery", "खाता रिकवरी")
            : t("Sign in", "साइन इन");
    document.title = `ShiftProof: ${title}`;
  }, [pathname, t]);
  return null;
}

function NotFound() {
  const { t } = usePreferences();
  return (
    <>
      <Header />
      <main id="main-content" className="not-found">
        <p className="auth-eyebrow">404</p>
        <h1>{t("This page is off shift.", "यह पेज अभी शिफ्ट पर नहीं है।")}</h1>
        <p>
          {t(
            "Let’s get you back to the right place.",
            "चलिए सही जगह पर वापस चलते हैं।",
          )}
        </p>
        <Link to="/" className="button button-primary">
          {t("Back to ShiftProof", "ShiftProof पर वापस जाएँ")}
        </Link>
      </main>
    </>
  );
}

function RolePage({
  children,
  admin = false,
}: {
  children: React.ReactNode;
  admin?: boolean;
}) {
  const role = useSession((state) => state.session?.user.role);
  const { t } = usePreferences();
  return role === "worker" || (admin && role !== "organization") ? (
    <ErrorNotice
      error={t(
        "Your account does not have permission to open this page.",
        "आपके खाते को यह पेज खोलने की अनुमति नहीं है।",
      )}
    />
  ) : (
    <>{children}</>
  );
}
const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 20_000, retry: 1, refetchOnWindowFocus: true },
    mutations: { retry: false },
  },
});
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <PreferencesProvider>
        <AppErrorBoundary>
          <BrowserRouter>
            <RouteEffects />
            <Suspense fallback={<Loading />}>
              <Routes>
                <Route path="/" element={<Landing />} />
                <Route path="/signin" element={<SignIn />} />
                <Route path="/signin/:role" element={<RoleLogin />} />
                <Route path="/signup" element={<SignUp />} />
                <Route path="/recover/:role" element={<Recovery />} />
                <Route path="/verify-email" element={<Activation />} />
                <Route path="/activate" element={<Activation />} />
                <Route path="/workspace" element={<Workspace />}>
                  <Route index element={<DashboardPage />} />
                  <Route
                    path="teams/:id"
                    element={
                      <RolePage>
                        <TeamDetailPage />
                      </RolePage>
                    }
                  />
                  <Route
                    path="supervisors/:id"
                    element={
                      <RolePage admin>
                        <SupervisorDetailPage />
                      </RolePage>
                    }
                  />
                  <Route
                    path="onboarding"
                    element={
                      <RolePage admin>
                        <OnboardingPage />
                      </RolePage>
                    }
                  />
                  <Route
                    path="attention"
                    element={
                      <RolePage>
                        <AttentionPage />
                      </RolePage>
                    }
                  />
                  <Route
                    path="departments/:id"
                    element={
                      <RolePage>
                        <DepartmentDetailPage />
                      </RolePage>
                    }
                  />
                  <Route
                    path="departments"
                    element={
                      <RolePage admin>
                        <DepartmentsPage />
                      </RolePage>
                    }
                  />
                  <Route
                    path="shifts"
                    element={
                      <RolePage>
                        <ShiftsPage />
                      </RolePage>
                    }
                  />
                  <Route
                    path="supervisors"
                    element={
                      <RolePage admin>
                        <SupervisorsPage />
                      </RolePage>
                    }
                  />
                  <Route
                    path="policies"
                    element={
                      <RolePage admin>
                        <PoliciesPage />
                      </RolePage>
                    }
                  />
                  <Route
                    path="workforce"
                    element={
                      <RolePage>
                        <WorkforcePage />
                      </RolePage>
                    }
                  />
                  <Route
                    path="workforce/:id"
                    element={
                      <RolePage>
                        <WorkerDetailPage />
                      </RolePage>
                    }
                  />
                  <Route path="tasks" element={<TasksPage />} />
                  <Route path="tasks/:id" element={<TaskDetailPage />} />
                  <Route path="record" element={<ReportComposer />} />
                  <Route path="drafts" element={<DraftsPage />} />
                  <Route path="reports" element={<ReportsPage />} />
                  <Route path="reports/:id" element={<ReportDetailPage />} />
                  <Route path="alerts" element={<AlertsPage />} />
                  <Route path="alerts/:id" element={<AlertsPage />} />
                  <Route
                    path="conflicts"
                    element={
                      <RolePage>
                        <ConflictsPage />
                      </RolePage>
                    }
                  />
                  <Route
                    path="conflicts/:id"
                    element={
                      <RolePage>
                        <ConflictsPage />
                      </RolePage>
                    }
                  />
                  <Route
                    path="follow-ups"
                    element={
                      <RolePage>
                        <FollowUpsPage />
                      </RolePage>
                    }
                  />
                  <Route path="handovers" element={<HandoversPage />} />
                  <Route path="handovers/:id" element={<HandoversPage />} />
                  <Route
                    path="analytics"
                    element={
                      <RolePage>
                        <AnalyticsPage />
                      </RolePage>
                    }
                  />
                  <Route
                    path="audit"
                    element={
                      <RolePage admin>
                        <AuditPage />
                      </RolePage>
                    }
                  />
                  <Route path="notifications" element={<NotificationsPage />} />
                  <Route path="settings" element={<SettingsPage />} />
                  <Route
                    path="*"
                    element={
                      <ErrorNotice error="This workspace page could not be found." />
                    }
                  />
                </Route>
                <Route path="*" element={<NotFound />} />
              </Routes>
            </Suspense>
          </BrowserRouter>
        </AppErrorBoundary>
      </PreferencesProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
if (import.meta.env.PROD && "serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    void navigator.serviceWorker.register("/sw.js").catch(() => undefined);
  });
}
