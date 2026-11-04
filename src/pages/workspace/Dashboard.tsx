import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  ArrowRight,
  ClipboardCheck,
  Download,
  Mic,
  ShieldCheck,
} from "lucide-react";
import { useCatalog } from "../../components/workspace/Workspace";
import {
  Empty,
  PageTitle,
  Panel,
  Status,
  When,
  formatDate,
  useWords,
} from "../../components/workspace/UI";
import { api, search } from "../../lib/api";
import { useSession } from "../../lib/session";
import { usePreferences } from "../../lib/preferences";
import type {
  AlertRecord,
  Analytics,
  Clarification,
  Handover,
  MetricRow,
  Paged,
  Report,
  Task,
} from "../../lib/types";
import { categories } from "./Reporting";
import { priorities, taskStatuses } from "./Tasks";
import { ShiftContext, SupervisorOrientation } from "./Operations";

const metricNames: Record<string, [string, string]> = {
  average_publication_delay_minutes: [
    "Average publication delay (minutes)",
    "प्रकाशन में औसत देरी (मिनट)",
  ],
  delayed_handovers: ["Delayed handovers", "देर से हैंडओवर"],
  average_resolution_hours: ["Average resolution hours", "समाधान के औसत घंटे"],
  average_alert_acknowledgement_minutes: [
    "Average alert receipt (minutes)",
    "अलर्ट पुष्टि का औसत (मिनट)",
  ],
  total_workers: ["Total workers", "कुल कर्मचारी"],
  active_workers: ["Active workers", "सक्रिय कर्मचारी"],
  absent_workers: ["Absent workers", "अनुपस्थित कर्मचारी"],
  active_departments: ["Active departments", "सक्रिय विभाग"],
  active_supervisors: ["Active supervisors", "सक्रिय पर्यवेक्षक"],
  total_tasks: ["Scheduled / due tasks", "निर्धारित / देय कार्य"],
  completed_tasks: ["Completed tasks", "पूरा किए कार्य"],
  closed_tasks: ["Closed tasks", "बंद कार्य"],
  pending_tasks: ["Pending tasks", "लंबित कार्य"],
  overdue_tasks: ["Overdue tasks", "समय सीमा पार कार्य"],
  blocked_tasks: ["Blocked tasks", "रुके कार्य"],
  task_completion_rate: ["Task completion rate", "कार्य पूर्णता दर"],
  on_time_completion_rate: ["On-time completion", "समय पर पूर्णता"],
  average_completion_hours: ["Average completion hours", "औसत पूर्णता घंटे"],
  safety_incidents: ["Safety incidents", "सुरक्षा घटनाएँ"],
  critical_incidents: ["Critical safety incidents", "गंभीर सुरक्षा घटनाएँ"],
  open_safety_issues: ["Open safety issues", "खुले सुरक्षा विषय"],
  resolved_safety_incidents: [
    "Resolved safety incidents",
    "सुलझी सुरक्षा घटनाएँ",
  ],
  quality_issues: ["Quality issues", "गुणवत्ता विषय"],
  open_quality_issues: ["Open quality issues", "खुले गुणवत्ता विषय"],
  resolved_quality_issues: ["Resolved quality issues", "सुलझे गुणवत्ता विषय"],
  recurring_quality_contexts: [
    "Recurring quality contexts",
    "दोहराए गुणवत्ता संदर्भ",
  ],
  submitted_reports: ["Submitted reports", "जमा रिपोर्ट"],
  reports_needing_attention: [
    "Reports needing attention",
    "ध्यान देने वाली रिपोर्ट",
  ],
  reports_awaiting_review: ["Reports awaiting review", "समीक्षा लंबित रिपोर्ट"],
  reports_awaiting_clarification: [
    "Awaiting clarification",
    "स्पष्टीकरण लंबित",
  ],
  reports_with_conflicts: ["Reports with conflicts", "विरोधाभास वाली रिपोर्ट"],
  issue_resolution_rate: ["Issue resolution rate", "समस्या समाधान दर"],
  issues_requiring_resolution: [
    "Issues requiring resolution",
    "समाधान चाहने वाले विषय",
  ],
  issues_resolved_in_period: [
    "Issues resolved in period",
    "अवधि में सुलझे विषय",
  ],
  published_handovers: ["Published handovers", "प्रकाशित हैंडओवर"],
  provisional_handovers: ["Provisional handovers", "अस्थायी हैंडओवर"],
  pending_acknowledgements: ["Pending receipts", "लंबित प्राप्ति पुष्टि"],
  handover_acknowledgement_rate: ["Handover receipt rate", "हैंडओवर पुष्टि दर"],
  critical_items_awaiting_acknowledgement: [
    "Pending critical receipts",
    "गंभीर विषयों की लंबित पुष्टि",
  ],
  critical_acknowledgement_rate: [
    "Critical item receipt rate",
    "गंभीर विषयों की पुष्टि दर",
  ],
  unresolved_conflicts: ["Unresolved conflicts", "अनसुलझे विरोधाभास"],
  unacknowledged_alerts: ["Unacknowledged alerts", "बिना पुष्टि के अलर्ट"],
  open_critical_issues: ["Open critical issues", "खुले गंभीर विषय"],
  pending_escalations: ["Pending escalations", "लंबित एस्केलेशन"],
  pending_corrective_actions: [
    "Pending corrective actions",
    "लंबित सुधारात्मक कार्य",
  ],
};
const chartColors = [
  "var(--primary)",
  "var(--secondary)",
  "var(--accent)",
  "var(--muted)",
  "var(--warning)",
  "var(--error)",
  "var(--success)",
];
const tooltipStyle = {
  background: "var(--surface)",
  border: "1px solid var(--border-strong)",
  borderRadius: 8,
  color: "var(--text)",
};

function Metrics({
  data,
  names,
  compare = false,
}: {
  data: Analytics;
  names: string[];
  compare?: boolean;
}) {
  const { t } = usePreferences();
  return (
    <div className="metric-grid">
      {names.map((key) => {
        const value = data.metrics[key];
        const label = metricNames[key] || [key.replaceAll("_", " "), key];
        const rate = key.endsWith("_rate");
        const previous = data.previous_metrics[key];
        return (
          <article className="metric-card" key={key}>
            <span>{t(label[0], label[1])}</span>
            <strong>
              {value === null || value === undefined
                ? "—"
                : `${value.toLocaleString(document.documentElement.lang)}${rate ? "%" : ""}`}
            </strong>
            {rate && value !== null && (
              <progress
                max={100}
                value={value}
                aria-label={t(label[0], label[1])}
              />
            )}
            {compare &&
              !key.includes("worker") &&
              key !== "active_departments" &&
              key !== "active_supervisors" &&
              previous !== undefined &&
              previous !== null && (
                <small>
                  {t("Previous period", "पिछली अवधि")}: {previous}
                  {rate ? "%" : ""}
                </small>
              )}
          </article>
        );
      })}
    </div>
  );
}

function TrendChart({
  data,
  keys,
}: {
  data: MetricRow[];
  keys: { key: string; label: string }[];
}) {
  const { t } = usePreferences();
  if (!data.some((row) => keys.some((key) => Number(row[key.key]) > 0)))
    return (
      <Empty>
        {t("No activity in this period.", "इस अवधि में गतिविधि नहीं है।")}
      </Empty>
    );
  return (
    <div
      className="chart-frame"
      role="img"
      aria-label={keys.map((key) => key.label).join(", ")}
    >
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={data}>
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis
            dataKey="date"
            tick={{ fill: "var(--muted)", fontSize: 11 }}
            tickFormatter={(value) => String(value).slice(5)}
            minTickGap={30}
          />
          <YAxis
            allowDecimals={false}
            tick={{ fill: "var(--muted)", fontSize: 11 }}
            width={35}
          />
          <Tooltip contentStyle={tooltipStyle} />
          <Legend />
          {keys.map((key, index) => (
            <Line
              isAnimationActive={false}
              key={key.key}
              dataKey={key.key}
              name={key.label}
              stroke={chartColors[index]}
              strokeWidth={2.5}
              dot={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
function ComparisonChart({
  data,
  keys,
  stacked = false,
}: {
  data: MetricRow[];
  keys: { key: string; label: string }[];
  stacked?: boolean;
}) {
  if (
    !data.length ||
    !data.some((row) => keys.some((key) => Number(row[key.key]) > 0))
  )
    return <Empty />;
  return (
    <div
      className="chart-frame"
      role="img"
      aria-label={keys.map((key) => key.label).join(", ")}
    >
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={data}>
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis
            dataKey="name"
            tick={{ fill: "var(--muted)", fontSize: 10 }}
            interval={0}
          />
          <YAxis
            width={35}
            allowDecimals={false}
            tick={{ fill: "var(--muted)", fontSize: 11 }}
          />
          <Tooltip contentStyle={tooltipStyle} />
          <Legend />
          {keys.map((key, index) => (
            <Bar
              isAnimationActive={false}
              dataKey={key.key}
              key={key.key}
              name={key.label}
              fill={chartColors[index]}
              stackId={stacked ? "work" : undefined}
              radius={stacked ? 0 : [4, 4, 0, 0]}
              maxBarSize={48}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
function Distribution({ data }: { data: MetricRow[] }) {
  const w = useWords();
  const localized: MetricRow[] = data.map((row) => ({
    ...row,
    name: w(String(row.name)),
  }));
  if (!data.some((row) => Number(row.value) > 0)) return <Empty />;
  return (
    <div
      className="chart-frame"
      role="img"
      aria-label={localized
        .map((row) => `${row.name}: ${row.value}`)
        .join(", ")}
    >
      <ResponsiveContainer width="100%" height={280}>
        <PieChart>
          <Pie
            isAnimationActive={false}
            data={localized}
            dataKey="value"
            nameKey="name"
            innerRadius={64}
            outerRadius={94}
            paddingAngle={2}
          >
            {localized.map((_, index) => (
              <Cell
                key={index}
                fill={chartColors[index % chartColors.length]}
              />
            ))}
          </Pie>
          <Tooltip contentStyle={tooltipStyle} />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

export function DashboardPage() {
  const role = useSession((state) => state.session?.user.role);
  return role === "worker" ? <WorkerDashboard /> : <ManagementDashboard />;
}

function WorkerDashboard() {
  const session = useSession((state) => state.session)!;
  const { departments, shifts } = useCatalog();
  const { t } = usePreferences();
  const w = useWords();
  const tasks = useQuery({
    queryKey: ["tasks", "home"],
    queryFn: () => api<Paged<Task>>("/tasks?limit=200"),
  });
  const handovers = useQuery({
    queryKey: ["handovers", "home"],
    queryFn: () => api<Handover[]>("/handovers"),
  });
  const questions = useQuery({
    queryKey: ["clarifications"],
    queryFn: () => api<Clarification[]>("/clarifications"),
  });
  const ownAssignments = useQuery({
    queryKey: ["shift-assignments"],
    queryFn: () =>
      api<{ shift_id: string; active: boolean }[]>("/shift-assignments"),
  });
  const pending =
    tasks.data?.items
      .filter((task) => task.status !== "closed")
      .sort(
        (a, b) =>
          Number(b.critical) - Number(a.critical) ||
          ({ urgent: 0, high: 1, normal: 2, low: 3 }[a.priority || "normal"] ??
            2) -
            ({ urgent: 0, high: 1, normal: 2, low: 3 }[
              b.priority || "normal"
            ] ?? 2) ||
          (a.deadline ? Date.parse(a.deadline) : Infinity) -
            (b.deadline ? Date.parse(b.deadline) : Infinity),
      ) || [];
  return (
    <>
      <PageTitle
        title={t(
          `Hello, ${session.user.name.split(" ")[0]}.`,
          `नमस्ते, ${session.user.name.split(" ")[0]}।`,
        )}
        description={t(
          "Your shift, with the details that matter.",
          "आपकी शिफ्ट, आवश्यक जानकारी के साथ।",
        )}
      />
      <div className="worker-context">
        <span>
          {session.memberships
            .map(
              (m) =>
                departments.data?.find((d) => d.id === m.department_id)?.name,
            )
            .filter(Boolean)
            .join(" · ")}
        </span>
        <span>
          {ownAssignments.data
            ?.filter((a) => a.active)
            .map((a) => shifts.data?.find((s) => s.id === a.shift_id)?.name)
            .filter(Boolean)
            .join(" · ") ||
            t("No shift assigned yet", "अभी शिफ्ट नहीं सौंपी गई")}
        </span>
        <span>
          {formatDate(new Date().toISOString(), session.organization.timezone)}
        </span>
      </div>
      <ShiftContext />
      <Link className="worker-record-cta" to="/workspace/record">
        <span className="record-cta-icon">
          <Mic size={34} />
        </span>
        <div>
          <h2>
            {t("What changed on your shift?", "आपकी शिफ्ट में क्या बदला?")}
          </h2>
          <p>
            {t(
              "Record a spoken update or write a report. No task selection needed.",
              "बोलकर या लिखकर अपडेट दें। कार्य चुनना आवश्यक नहीं है।",
            )}
          </p>
        </div>
        <ArrowRight />
      </Link>
      <div className="work-actions section-actions">
        <Link className="button button-outline" to="/workspace/reports">
          {t("My reports", "मेरी रिपोर्ट")}
        </Link>
        <Link className="button button-outline" to="/workspace/drafts">
          {w("Local drafts")}
        </Link>
        <Link className="button button-outline" to="/workspace/handovers">
          {w("Handovers")}
        </Link>
        <Link className="button button-outline" to="/workspace/alerts">
          {t("My alerts", "मेरे अलर्ट")}
        </Link>
      </div>
      {questions.data?.some((question) => !question.responded_at) && (
        <Panel title={t("Your response is needed", "आपका उत्तर आवश्यक है")}>
          {questions.data
            .filter((question) => !question.responded_at)
            .map((question) => (
              <Link
                className="work-list-row"
                key={question.id}
                to={`/workspace/reports/${question.report_id}`}
              >
                <p>{question.question}</p>
                <span className="text-link">{t("Respond", "उत्तर दें")} →</span>
              </Link>
            ))}
        </Panel>
      )}
      <Panel
        title={t("Your current work", "आपका मौजूदा काम")}
        action={
          <Link className="text-link" to="/workspace/tasks">
            {t("View all", "सभी देखें")} →
          </Link>
        }
      >
        <When loading={tasks.isLoading} error={tasks.error}>
          {!pending.length ? (
            <Empty>
              {t(
                "You have no unfinished assigned tasks. You can still report an update.",
                "आपका कोई अधूरा सौंपा कार्य नहीं है। फिर भी आप अपडेट दे सकते हैं।",
              )}
            </Empty>
          ) : (
            pending.slice(0, 6).map((task) => (
              <Link
                className="work-list-row"
                to={`/workspace/tasks/${task.id}`}
                key={task.id}
              >
                <span className="list-icon">
                  <ClipboardCheck size={22} />
                </span>
                <div className="row-grow">
                  <strong>{task.title}</strong>
                  <p>
                    {formatDate(task.deadline, session.organization.timezone)}
                  </p>
                  {task.critical && (
                    <span className="work-warning">{w("Critical")}</span>
                  )}
                </div>
                <Status value={task.status} />
              </Link>
            ))
          )}
        </When>
      </Panel>
      <Panel
        title={t("Incoming context", "आने वाली शिफ्ट का संदर्भ")}
        action={
          <Link className="text-link" to="/workspace/handovers">
            {w("Handovers")} →
          </Link>
        }
      >
        {!handovers.data?.length ? (
          <Empty>
            {t(
              "Your department’s published handovers will appear here.",
              "विभाग के प्रकाशित हैंडओवर यहाँ दिखेंगे।",
            )}
          </Empty>
        ) : (
          handovers.data.slice(0, 3).map((handover) => (
            <Link
              className="work-list-row"
              key={handover.id}
              to={`/workspace/handovers/${handover.id}`}
            >
              <div>
                <strong>
                  {
                    departments.data?.find(
                      (d) => d.id === handover.department_id,
                    )?.name
                  }
                </strong>
                <p>
                  {handover.shift_date} · {t("version", "संस्करण")}{" "}
                  {handover.latest_version}
                </p>
              </div>
              <Status value={handover.status} />
            </Link>
          ))
        )}
      </Panel>
    </>
  );
}

function ManagementDashboard() {
  const session = useSession((state) => state.session)!;
  const admin = session.user.role === "organization";
  const { t } = usePreferences();
  const w = useWords();
  const [days, setDays] = useState("30");
  const end = new Date().toISOString().slice(0, 10);
  const start = new Date(Date.now() - (Number(days) - 1) * 86400000)
    .toISOString()
    .slice(0, 10);
  const analytics = useQuery({
    queryKey: ["analytics", start, end],
    queryFn: () => api<Analytics>(`/analytics${search({ start, end })}`),
  });
  const alerts = useQuery({
    queryKey: ["alerts", "home"],
    queryFn: () => api<AlertRecord[]>("/alerts"),
  });
  const reports = useQuery({
    queryKey: ["reports", "attention"],
    queryFn: () => api<Paged<Report>>("/reports?needs_attention=true&limit=8"),
    enabled: !admin,
  });
  return (
    <>
      <PageTitle
        title={
          admin
            ? "Overview"
            : t("Your department, in view.", "आपके विभाग की स्पष्ट तस्वीर।")
        }
        description={t(
          "See what is moving, what needs a decision, and what the next shift must know.",
          "देखें क्या आगे बढ़ रहा है, कहाँ निर्णय चाहिए और अगली शिफ्ट को क्या जानना है।",
        )}
      >
        <label className="compact-select">
          {t("Date range", "तारीख सीमा")}
          <select
            value={days}
            onChange={(event) => setDays(event.target.value)}
          >
            <option value="7">{t("Last 7 days", "पिछले 7 दिन")}</option>
            <option value="30">{t("Last 30 days", "पिछले 30 दिन")}</option>
            <option value="90">{t("Last 90 days", "पिछले 90 दिन")}</option>
          </select>
        </label>
      </PageTitle>
      {!session.organization.active && (
        <div className="setup-banner">
          <ShieldCheck size={25} />
          <div>
            <h2>
              {t(
                "Finish setting up your workspace",
                "कार्यस्थल का सेटअप पूरा करें",
              )}
            </h2>
            <p>
              {t(
                "Operations activate after the five required onboarding steps are complete.",
                "पाँच आवश्यक चरण पूरे होने पर संचालन सक्रिय होगा।",
              )}
            </p>
          </div>
          <Link className="button button-primary" to="/workspace/onboarding">
            {t("Continue setup", "सेटअप जारी रखें")}
          </Link>
        </div>
      )}
      <ShiftContext />
      <SupervisorOrientation />
      <When loading={analytics.isLoading} error={analytics.error}>
        {analytics.data && (
          <>
            <Metrics
              data={analytics.data}
              names={
                admin
                  ? [
                      "active_departments",
                      "active_workers",
                      "active_supervisors",
                      "pending_tasks",
                      "open_critical_issues",
                      "pending_escalations",
                    ]
                  : [
                      "pending_tasks",
                      "reports_awaiting_review",
                      "overdue_tasks",
                      "unacknowledged_alerts",
                      "unresolved_conflicts",
                      "pending_acknowledgements",
                    ]
              }
              compare
            />
            <div className="work-two-column">
              <Panel title={t("Work over time", "समय के साथ कार्य")}>
                <TrendChart
                  data={analytics.data.trends}
                  keys={[
                    {
                      key: "completed",
                      label: t("Completed tasks", "पूरा किए कार्य"),
                    },
                    { key: "reports", label: t("Reports", "रिपोर्ट") },
                  ]}
                />
              </Panel>
              <Panel title={t("Task status", "कार्य स्थिति")}>
                <Distribution data={analytics.data.task_status} />
              </Panel>
            </div>
            <Panel
              title={t("Department health", "विभाग की स्थिति")}
              action={
                <Link className="text-link" to="/workspace/analytics">
                  {w("Analytics")} →
                </Link>
              }
            >
              {analytics.data.departments.map((dept) => (
                <Link
                  className="department-health"
                  key={dept.id}
                  to={`/workspace/analytics?department=${dept.id}`}
                >
                  <div>
                    <h3>{dept.name}</h3>
                    <Status value={dept.health} />
                  </div>
                  <div>
                    <span>
                      {t("Closed", "बंद")}: <strong>{dept.closed}</strong>
                    </span>
                    <span>
                      {t("Pending", "लंबित")}: <strong>{dept.pending}</strong>
                    </span>
                    <span>
                      {t("Overdue", "समय सीमा पार")}:{" "}
                      <strong>{dept.overdue}</strong>
                    </span>
                    <span>
                      {t("Critical", "गंभीर")}: <strong>{dept.critical}</strong>
                    </span>
                  </div>
                </Link>
              ))}
            </Panel>
            {analytics.data.coverage.some(
              (row) => !row.primary || !row.backup,
            ) && (
              <Panel
                title={t(
                  "Coverage needs attention",
                  "जिम्मेदारी कवरेज पर ध्यान दें",
                )}
              >
                {analytics.data.coverage
                  .filter((row) => !row.primary || !row.backup)
                  .map((row) => (
                    <div className="work-list-row" key={row.department_id}>
                      <strong>{row.department}</strong>
                      <p className="work-warning">
                        {!row.primary &&
                          t(
                            "No active primary supervisor. ",
                            "सक्रिय मुख्य पर्यवेक्षक नहीं है। ",
                          )}
                        {!row.backup &&
                          t(
                            "No active backup supervisor.",
                            "सक्रिय बैकअप पर्यवेक्षक नहीं है।",
                          )}
                      </p>
                    </div>
                  ))}
              </Panel>
            )}
          </>
        )}
      </When>
      <div className="work-two-column">
        <Panel
          title={t("Open critical concerns", "खुले गंभीर विषय")}
          action={
            <Link className="text-link" to="/workspace/alerts">
              {w("Alerts")} →
            </Link>
          }
        >
          {!alerts.data?.some((alert) => alert.status !== "resolved") ? (
            <Empty />
          ) : (
            alerts.data
              .filter((alert) => alert.status !== "resolved")
              .slice(0, 6)
              .map((alert) => (
                <Link
                  className="work-list-row"
                  to={`/workspace/alerts/${alert.id}`}
                  key={alert.id}
                >
                  <div>
                    <strong>{alert.title}</strong>
                    <p>
                      {formatDate(
                        alert.created_at,
                        session.organization.timezone,
                      )}
                    </p>
                  </div>
                  <Status value={alert.status} />
                </Link>
              ))
          )}
        </Panel>
        {!admin ? (
          <Panel
            title={t("Needs attention", "ध्यान आवश्यक")}
            action={
              <Link className="text-link" to="/workspace/reports">
                {w("Reports")} →
              </Link>
            }
          >
            {!reports.data?.items.length ? (
              <Empty />
            ) : (
              reports.data.items.map((report) => (
                <Link
                  className="work-list-row"
                  key={report.id}
                  to={`/workspace/reports/${report.id}`}
                >
                  <div>
                    <strong>{w(report.category)}</strong>
                    <p>
                      {formatDate(
                        report.occurred_at,
                        session.organization.timezone,
                      )}
                    </p>
                  </div>
                  <Status value={report.status} />
                </Link>
              ))
            )}
          </Panel>
        ) : (
          analytics.data && (
            <Panel title={t("Handover performance", "हैंडओवर प्रदर्शन")}>
              <Metrics
                data={analytics.data}
                names={[
                  "handover_acknowledgement_rate",
                  "critical_acknowledgement_rate",
                ]}
              />
              <Link className="text-link" to="/workspace/handovers">
                {w("Handovers")} →
              </Link>
            </Panel>
          )
        )}
      </div>
    </>
  );
}

export function AnalyticsPage() {
  const { departments, teams, shifts } = useCatalog();
  const { t } = usePreferences();
  const w = useWords();
  const [family, setFamily] = useState("tasks");
  const [filter, setFilter] = useState({
    start: new Date(Date.now() - 29 * 86400000).toISOString().slice(0, 10),
    end: new Date().toISOString().slice(0, 10),
    department_id: new URLSearchParams(location.search).get("department") || "",
    team_id: "",
    shift_id: "",
    priority: "",
    category: "",
    status: "",
  });
  const data = useQuery({
    queryKey: ["analytics", filter],
    queryFn: () => api<Analytics>(`/analytics${search(filter)}`),
  });
  const families: Record<string, { label: string; metrics: string[] }> = {
    workforce: {
      label: t("Workforce", "कर्मचारी"),
      metrics: ["total_workers", "active_workers", "absent_workers"],
    },
    tasks: {
      label: t("Task performance", "कार्य प्रदर्शन"),
      metrics: [
        "total_tasks",
        "completed_tasks",
        "closed_tasks",
        "pending_tasks",
        "overdue_tasks",
        "blocked_tasks",
        "task_completion_rate",
        "on_time_completion_rate",
        "average_completion_hours",
      ],
    },
    safety: {
      label: t("Safety", "सुरक्षा"),
      metrics: [
        "safety_incidents",
        "critical_incidents",
        "open_safety_issues",
        "resolved_safety_incidents",
      ],
    },
    quality: {
      label: t("Quality", "गुणवत्ता"),
      metrics: [
        "quality_issues",
        "open_quality_issues",
        "resolved_quality_issues",
        "recurring_quality_contexts",
      ],
    },
    reporting: {
      label: t("Reporting", "रिपोर्टिंग"),
      metrics: [
        "submitted_reports",
        "reports_needing_attention",
        "reports_awaiting_clarification",
        "reports_with_conflicts",
        "issue_resolution_rate",
        "average_resolution_hours",
      ],
    },
    handovers: {
      label: t("Handovers", "हैंडओवर"),
      metrics: [
        "published_handovers",
        "provisional_handovers",
        "pending_acknowledgements",
        "critical_items_awaiting_acknowledgement",
        "handover_acknowledgement_rate",
        "average_publication_delay_minutes",
        "delayed_handovers",
      ],
    },
    supervisors: {
      label: t("Supervisor operations", "पर्यवेक्षक संचालन"),
      metrics: [
        "reports_awaiting_review",
        "pending_corrective_actions",
        "unresolved_conflicts",
        "unacknowledged_alerts",
        "overdue_tasks",
        "pending_acknowledgements",
        "average_alert_acknowledgement_minutes",
      ],
    },
  };
  const download = () => {
    if (!data.data) return;
    const rows = [
      ["Metric", "Value", "Start", "End", "Timezone"],
      ...Object.entries(data.data.metrics).map(([key, value]) => [
        metricNames[key]?.[0] || key,
        value ?? "",
        filter.start,
        filter.end,
        data.data!.period.timezone,
      ]),
    ];
    const csv = rows
      .map((row) =>
        row
          .map((value) => `"${String(value).replaceAll('"', '""')}"`)
          .join(","),
      )
      .join("\n");
    const url = URL.createObjectURL(
      new Blob([csv], { type: "text/csv;charset=utf-8" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = `shiftproof-metrics-${filter.start}-${filter.end}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };
  const selected = data.data;
  return (
    <>
      <PageTitle
        title="Analytics"
        description={t(
          "Actual operational records, consistent periods, and visible calculation rules.",
          "वास्तविक संचालन रिकॉर्ड, समान अवधि और स्पष्ट गणना के नियम।",
        )}
      >
        <button
          className="button button-outline"
          disabled={!selected}
          onClick={download}
        >
          <Download size={17} />
          {t("Export metrics", "आँकड़े निर्यात करें")}
        </button>
      </PageTitle>
      <div className="work-filters analytics-filters">
        {(["start", "end"] as const).map((key) => (
          <label key={key}>
            {w(key === "start" ? "Start date" : "End date")}
            <input
              type="date"
              value={filter[key]}
              onChange={(event) =>
                setFilter({ ...filter, [key]: event.target.value })
              }
            />
          </label>
        ))}
        {(
          [
            {
              key: "department_id",
              label: "Department",
              options: departments.data?.map((d) => ({
                value: d.id,
                label: d.name,
              })),
            },
            {
              key: "team_id",
              label: "Team",
              options: teams.data
                ?.filter(
                  (team) =>
                    !filter.department_id ||
                    team.department_id === filter.department_id,
                )
                .map((team) => ({ value: team.id, label: team.name })),
            },
            {
              key: "shift_id",
              label: "Shift",
              options: shifts.data?.map((s) => ({
                value: s.id,
                label: s.name,
              })),
            },
            {
              key: "priority",
              label: "Priority",
              options: priorities.map((value) => ({ value, label: value })),
            },
            {
              key: "category",
              label: "Category",
              options: categories.map((value) => ({ value, label: value })),
            },
            {
              key: "status",
              label: "Status",
              options: [
                ...new Set([...taskStatuses, "submitted", "resolved"]),
              ].map((value) => ({ value, label: value })),
            },
          ] as const
        ).map((item) => (
          <label key={item.key}>
            {w(item.label)}
            <select
              value={filter[item.key]}
              onChange={(event) =>
                setFilter({
                  ...filter,
                  [item.key]: event.target.value,
                  ...(item.key === "department_id" ? { team_id: "" } : {}),
                })
              }
            >
              <option value="">{w("All")}</option>
              {item.options?.map((option) => (
                <option key={option.value} value={option.value}>
                  {w(option.label)}
                </option>
              ))}
            </select>
          </label>
        ))}
      </div>
      <div
        className="analytics-tabs"
        role="tablist"
        aria-label={t("Analytics categories", "विश्लेषण श्रेणियाँ")}
      >
        {Object.entries(families).map(([key, value]) => (
          <button
            role="tab"
            aria-selected={family === key}
            key={key}
            onClick={() => setFamily(key)}
          >
            {value.label}
          </button>
        ))}
      </div>
      <When loading={data.isLoading} error={data.error}>
        {selected && (
          <>
            <Metrics data={selected} names={families[family].metrics} compare />
            {!selected.has_data && (
              <Empty>
                {t(
                  "Charts will use your organization’s records as work is recorded.",
                  "काम दर्ज होने पर चार्ट संगठन के वास्तविक रिकॉर्ड दिखाएँगे।",
                )}
              </Empty>
            )}
            {family === "workforce" && (
              <div className="work-two-column">
                <Panel
                  title={t("Workers by department", "विभाग के अनुसार कर्मचारी")}
                >
                  <ComparisonChart
                    data={selected.departments}
                    keys={[{ key: "workers", label: w("Workforce") }]}
                  />
                </Panel>
                <Panel
                  title={t("Workers by shift", "शिफ्ट के अनुसार कर्मचारी")}
                >
                  <ComparisonChart
                    data={selected.shifts}
                    keys={[
                      {
                        key: "workers",
                        label: t("Scheduled workers", "निर्धारित कर्मचारी"),
                      },
                    ]}
                  />
                </Panel>
                <Panel title={t("Workers by team", "टीम के अनुसार कर्मचारी")}>
                  <ComparisonChart
                    data={selected.teams}
                    keys={[{ key: "workers", label: w("Workforce") }]}
                  />
                </Panel>
                <Panel title={t("Current availability", "मौजूदा उपलब्धता")}>
                  <Distribution
                    data={[
                      {
                        name: t(
                          "Active, not marked absent",
                          "सक्रिय, अनुपस्थित नहीं",
                        ),
                        value: Math.max(
                          0,
                          (selected.metrics.active_workers || 0) -
                            (selected.metrics.absent_workers || 0),
                        ),
                      },
                      {
                        name: t("Absent / unavailable", "अनुपस्थित / अनुपलब्ध"),
                        value: selected.metrics.absent_workers || 0,
                      },
                    ]}
                  />
                </Panel>
              </div>
            )}
            {family === "tasks" && (
              <>
                <Panel
                  title={t("Deadline completion", "समय सीमा के अनुसार पूर्णता")}
                >
                  <Distribution
                    data={[
                      {
                        name: t("On time", "समय पर"),
                        value: selected.metrics.on_time_completed,
                      },
                      {
                        name: t("Delayed", "देर से"),
                        value: selected.metrics.delayed_completed,
                      },
                    ]}
                  />
                </Panel>
                <div className="work-two-column">
                  <Panel title={t("Completion trend", "पूर्णता का रुझान")}>
                    <TrendChart
                      data={selected.trends}
                      keys={[
                        { key: "completed", label: t("Completed", "पूरा") },
                      ]}
                    />
                  </Panel>
                  <Panel title={t("Status distribution", "स्थिति वितरण")}>
                    <Distribution data={selected.task_status} />
                  </Panel>
                  <Panel
                    title={t(
                      "Department task composition",
                      "विभाग के कार्यों की स्थिति",
                    )}
                  >
                    <ComparisonChart
                      data={selected.departments.map((row) => ({
                        ...row,
                        pending: Math.max(
                          0,
                          Number(row.pending) - Number(row.blocked),
                        ),
                      }))}
                      keys={[
                        { key: "closed", label: t("Closed", "बंद") },
                        { key: "pending", label: t("Pending", "लंबित") },
                        { key: "blocked", label: t("Blocked", "रुका") },
                      ]}
                      stacked
                    />
                  </Panel>
                  <Panel title={t("Priority distribution", "प्राथमिकता वितरण")}>
                    <Distribution data={selected.task_priority} />
                  </Panel>
                </div>
                <Panel
                  title={t(
                    "Current versus previous period",
                    "वर्तमान और पिछली अवधि",
                  )}
                >
                  <ComparisonChart
                    data={[
                      "closed_tasks",
                      "overdue_tasks",
                      "blocked_tasks",
                    ].map((key) => ({
                      name: t(...metricNames[key]),
                      current: selected.metrics[key],
                      previous: selected.previous_metrics[key],
                    }))}
                    keys={[
                      {
                        key: "current",
                        label: t("Current period", "वर्तमान अवधि"),
                      },
                      {
                        key: "previous",
                        label: t("Previous period", "पिछली अवधि"),
                      },
                    ]}
                  />
                </Panel>
              </>
            )}
            {(family === "safety" || family === "quality") && (
              <>
                <div className="work-two-column">
                  <Panel title={t("Issue trend", "समस्या का रुझान")}>
                    <TrendChart
                      data={selected.trends}
                      keys={[{ key: family, label: families[family].label }]}
                    />
                  </Panel>
                  <Panel title={t("Department comparison", "विभाग तुलना")}>
                    <ComparisonChart
                      data={selected.departments}
                      keys={[{ key: family, label: families[family].label }]}
                    />
                  </Panel>
                  <Panel title={t("Shift comparison", "शिफ्ट तुलना")}>
                    <ComparisonChart
                      data={selected.shifts}
                      keys={[{ key: family, label: families[family].label }]}
                    />
                  </Panel>
                  <Panel
                    title={
                      family === "quality"
                        ? t("Recurring contexts", "दोहराए संदर्भ")
                        : t(
                            "Critical versus other safety incidents",
                            "गंभीर और अन्य सुरक्षा घटनाएँ",
                          )
                    }
                  >
                    {family === "quality" ? (
                      <Distribution data={selected.recurring_quality} />
                    ) : (
                      <Distribution
                        data={[
                          {
                            name: t("Critical", "गंभीर"),
                            value: selected.metrics.critical_incidents,
                          },
                          {
                            name: t(
                              "Other safety reports",
                              "अन्य सुरक्षा रिपोर्ट",
                            ),
                            value:
                              (selected.metrics.safety_incidents || 0) -
                              (selected.metrics.critical_incidents || 0),
                          },
                        ]}
                      />
                    )}
                  </Panel>
                </div>
                <Panel
                  title={t(
                    "Shift and department issue patterns",
                    "शिफ्ट और विभाग के विषयों का पैटर्न",
                  )}
                >
                  <div className="issue-heatmap">
                    {selected.heatmap.map((cell, index) => (
                      <div
                        key={index}
                        style={{
                          background: `color-mix(in srgb, var(--primary) ${Math.min(70, 6 + Number(cell.issues) * 12)}%, var(--surface))`,
                        }}
                      >
                        <span>{cell.department}</span>
                        <small>{cell.shift}</small>
                        <strong>{cell.issues}</strong>
                      </div>
                    ))}
                  </div>
                </Panel>
              </>
            )}
            {family === "reporting" && (
              <div className="work-two-column">
                <Panel title={t("Report volume", "रिपोर्ट की संख्या")}>
                  <TrendChart
                    data={selected.trends}
                    keys={[{ key: "reports", label: w("Reports") }]}
                  />
                </Panel>
                <Panel title={t("Category distribution", "श्रेणी वितरण")}>
                  <Distribution data={selected.report_categories} />
                </Panel>
                <Panel title={t("Department reporting", "विभाग की रिपोर्टिंग")}>
                  <ComparisonChart
                    data={selected.departments}
                    keys={[{ key: "reports", label: w("Reports") }]}
                  />
                </Panel>
                <Panel title={t("Shift reporting", "शिफ्ट की रिपोर्टिंग")}>
                  <ComparisonChart
                    data={selected.shifts}
                    keys={[{ key: "reports", label: w("Reports") }]}
                  />
                </Panel>
              </div>
            )}
            {family === "handovers" && (
              <Panel
                title={t(
                  "Department handover performance",
                  "विभाग का हैंडओवर प्रदर्शन",
                )}
              >
                <ComparisonChart
                  data={selected.handover_departments}
                  keys={[
                    {
                      key: "published",
                      label: t("Published handovers", "प्रकाशित हैंडओवर"),
                    },
                    {
                      key: "pending",
                      label: t("Pending receipts", "लंबित प्राप्ति पुष्टि"),
                    },
                    {
                      key: "critical_pending",
                      label: t(
                        "Critical receipts pending",
                        "गंभीर विषयों की पुष्टि लंबित",
                      ),
                    },
                  ]}
                />
              </Panel>
            )}
            {family === "handovers" && (
              <div className="work-two-column">
                <Panel
                  title={t(
                    "Publication and receipt trend",
                    "प्रकाशन और प्राप्ति का रुझान",
                  )}
                >
                  <TrendChart
                    data={selected.trends}
                    keys={[
                      { key: "handovers", label: w("Handovers") },
                      {
                        key: "acknowledgements",
                        label: t("Receipts", "प्राप्ति पुष्टि"),
                      },
                    ]}
                  />
                </Panel>
                <Panel title={t("Publication status", "प्रकाशन की स्थिति")}>
                  <Distribution
                    data={[
                      {
                        name: t("Published", "प्रकाशित"),
                        value: selected.metrics.published_handovers,
                      },
                      {
                        name: t("Provisional", "अस्थायी"),
                        value: selected.metrics.provisional_handovers,
                      },
                    ]}
                  />
                </Panel>
              </div>
            )}
            {family === "supervisors" && (
              <Panel
                title={t(
                  "Supervisor operational workload",
                  "पर्यवेक्षक का संचालन कार्यभार",
                )}
              >
                <ComparisonChart
                  data={selected.supervisor_workload}
                  keys={[
                    { key: "reports", label: w("Reports") },
                    { key: "approvals", label: t("Approvals", "मंज़ूरी") },
                    { key: "alerts", label: w("Alerts") },
                  ]}
                />
              </Panel>
            )}
            {family === "supervisors" && (
              <div className="work-two-column">
                <Panel
                  title={t("Department outstanding work", "विभाग के लंबित काम")}
                >
                  <ComparisonChart
                    data={selected.departments}
                    keys={[
                      { key: "pending", label: w("Pending") },
                      { key: "overdue", label: w("Overdue") },
                      { key: "critical", label: w("Critical") },
                    ]}
                  />
                </Panel>
                <Panel
                  title={t("Open work distribution", "खुले कार्यों का वितरण")}
                >
                  <Distribution
                    data={families.supervisors.metrics.map((key) => ({
                      name: t(...metricNames[key]),
                      value: selected.metrics[key],
                    }))}
                  />
                </Panel>
              </div>
            )}
            <Panel
              title={t("Drill down by department", "विभाग का विस्तृत दृश्य")}
            >
              <div className="work-actions">
                {selected.departments.map((dept) => (
                  <button
                    key={dept.id}
                    className="button button-outline"
                    onClick={() =>
                      setFilter({
                        ...filter,
                        department_id: dept.id,
                        team_id: "",
                      })
                    }
                  >
                    {dept.name} →
                  </button>
                ))}
              </div>
            </Panel>
            <details className="metric-definitions">
              <summary>
                {t(
                  "Calculation rules and period definitions",
                  "गणना के नियम और अवधि की परिभाषा",
                )}
              </summary>
              {Object.entries(selected.cohorts).map(([key, value]) => (
                <p key={key}>
                  <strong>{key}: </strong>
                  {value}
                </p>
              ))}
              <p>
                {t(
                  "Healthy: no open critical alerts, overdue or blocked tasks in the selected scope. Needs attention: overdue or blocked work. Critical: at least one open critical alert.",
                  "स्वस्थ: चुने क्षेत्र में खुले गंभीर अलर्ट, समय सीमा पार या रुके कार्य नहीं। ध्यान आवश्यक: देर या रुकावट। गंभीर: कम से कम एक खुला गंभीर अलर्ट।",
                )}
              </p>
            </details>
          </>
        )}
      </When>
    </>
  );
}
