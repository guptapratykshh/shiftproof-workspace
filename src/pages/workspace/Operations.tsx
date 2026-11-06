import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useState } from "react";
import { CheckCircle2 } from "lucide-react";
import { useCatalog } from "../../components/workspace/Workspace";
import {
  ActionButton,
  Empty,
  PageTitle,
  Panel,
  Status,
  When,
  formatDate,
  useWords,
} from "../../components/workspace/UI";
import { api, post, put, search } from "../../lib/api";
import { useSession } from "../../lib/session";
import { usePreferences } from "../../lib/preferences";
import type {
  Department,
  History,
  Membership,
  Team,
  Person,
  Task,
  ShiftAssignment,
} from "../../lib/types";

type Context = {
  as_of: string;
  shifts: {
    id: string;
    name: string;
    starts_at: string;
    ends_at: string;
    shift_date: string;
  }[];
  takeovers: { id: string; department_id: string; expires_at: string }[];
  attention: {
    id: string;
    kind: string;
    title: string;
    reason: string;
    department_id: string;
    responsible: string | null;
    status: string;
    rank: number;
    created_at: string;
    href: string;
  }[];
};
export function ShiftContext() {
  const session = useSession((state) => state.session)!;
  const { t } = usePreferences();
  const data = useQuery({
    queryKey: ["workspace-context"],
    queryFn: () => api<Context>("/workspace/context"),
    refetchInterval: 60_000,
  });
  return (
    <>
      {data.data?.takeovers.map((takeover) => (
        <div
          className="work-warning setup-banner"
          role="status"
          key={takeover.id}
        >
          {t(
            "Temporary operational access is active until",
            "अस्थायी संचालन अनुमति सक्रिय है, समाप्ति",
          )}{" "}
          {formatDate(takeover.expires_at, session.organization.timezone)}.{" "}
          <Link to="/workspace/policies">
            {t("Review or end takeover", "अस्थायी अनुमति देखें या समाप्त करें")}{" "}
            →
          </Link>
        </div>
      ))}
      <div className="current-shift-strip">
        <span>
          {formatDate(new Date().toISOString(), session.organization.timezone)}
        </span>
        {data.data?.shifts.map((shift) => (
          <span key={shift.id}>
            <strong>{shift.name}</strong> ·{" "}
            {Math.max(
              0,
              Math.ceil((Date.parse(shift.ends_at) - Date.now()) / 60000),
            )}{" "}
            {t("minutes until handover", "मिनट में हैंडओवर")}
          </span>
        ))}
      </div>
    </>
  );
}

export function SupervisorOrientation() {
  const session = useSession((state) => state.session)!;
  const setSession = useSession((state) => state.setSession);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { departments, teams } = useCatalog();
  const { t } = usePreferences();
  if (
    session.user.role !== "supervisor" ||
    session.user.profile.orientation_completed_at
  )
    return null;

  const currentSavedStep = Math.min(
    5,
    Math.max(1, Number(session.user.profile.orientation_step || 1)),
  );
  const [selectedStep, setSelectedStep] = useState<number | null>(null);
  const step = selectedStep || currentSavedStep;

  const rawSkipped: number[] = session.user.profile.orientation_skipped
    ? String(session.user.profile.orientation_skipped)
      .split(",")
      .map((s) => Number(s.trim()))
      .filter(Boolean)
    : [];
  const [skipped, setSkipped] = useState<number[]>(rawSkipped);
  const [completed, setCompleted] = useState<number[]>(() => {
    const list: number[] = [];
    for (let i = 1; i < currentSavedStep; i++) {
      if (!rawSkipped.includes(i)) list.push(i);
    }
    return list;
  });

  const steps = [
    {
      number: 1,
      title: t("Your departments and permissions", "आपके विभाग और अनुमतियाँ"),
      description: session.memberships
        .filter((m) => m.active)
        .map(
          (m) =>
            `${departments.data?.find((d) => d.id === m.department_id)?.name || ""}: ${m.permissions.join(", ")}`,
        )
        .join(" · "),
      href: "/workspace/settings",
    },
    {
      number: 2,
      title: t("Review your teams and people", "अपनी टीम और लोगों को देखें"),
      description:
        teams.data?.map((team) => team.name).join(" · ") ||
        t(
          "Your assigned teams appear in the workforce directory.",
          "निर्धारित टीमें कर्मचारी सूची में दिखाई देंगी।",
        ),
      href: "/workspace/workforce",
    },
    {
      number: 3,
      title: t("Confirm shift coverage", "शिफ्ट की जिम्मेदारी जाँचें"),
      description: t(
        "Review worker schedules and your primary or backup responsibilities.",
        "कर्मचारी शेड्यूल और अपनी मुख्य या बैकअप जिम्मेदारी जाँचें।",
      ),
      href: "/workspace/shifts",
    },
    {
      number: 4,
      title: t("Read incoming context", "आने वाला संदर्भ पढ़ें"),
      description: t(
        "Confirm receipt of the handover and each critical item separately. Open work keeps its owner until explicitly reassigned.",
        "हैंडओवर और हर गंभीर विषय की अलग पुष्टि करें। पुनः सौंपे जाने तक खुले काम की जिम्मेदारी बनी रहती है।",
      ),
      href: "/workspace/handovers",
    },
    {
      number: 5,
      title: t(
        "Start with what needs attention",
        "ध्यान देने वाले विषय से शुरू करें",
      ),
      description: t(
        "Safety, approvals, conflicts and blocked work appear first. Routine activity remains in reports.",
        "सुरक्षा, मंज़ूरी, विरोधाभास और रुके कार्य पहले आते हैं। नियमित गतिविधि रिपोर्ट में रहती है।",
      ),
      href: "/workspace/attention",
    },
  ];

  const current = steps[step - 1];

  const isLastAction = (actingStep: number, isSkipping: boolean) => {
    const newCompleted = new Set(completed);
    const newSkipped = new Set(skipped);
    if (isSkipping) {
      newSkipped.add(actingStep);
      newCompleted.delete(actingStep);
    } else {
      newCompleted.add(actingStep);
      newSkipped.delete(actingStep);
    }
    const allHandled = [1, 2, 3, 4, 5].every(
      (n) => newCompleted.has(n) || newSkipped.has(n),
    );
    return allHandled || actingStep >= 5;
  };

  const finishOrientation = async () => {
    await post("/orientation/complete");
    if (session) {
      setSession({
        ...session,
        user: {
          ...session.user,
          profile: {
            ...session.user.profile,
            orientation_completed_at: new Date().toISOString(),
          },
        },
      });
    }
    void queryClient.invalidateQueries({ queryKey: ["session"] });
    navigate("/workspace");
  };

  const handleContinue = async () => {
    const newCompleted = Array.from(new Set([...completed, step]));
    const newSkipped = skipped.filter((s) => s !== step);
    setCompleted(newCompleted);
    setSkipped(newSkipped);

    if (isLastAction(step, false)) {
      await finishOrientation();
    } else {
      const nextStep = Math.min(5, step + 1);
      await put("/orientation", { step: nextStep, skipped: newSkipped });
      if (session) {
        setSession({
          ...session,
          user: {
            ...session.user,
            profile: {
              ...session.user.profile,
              orientation_step: String(nextStep),
              orientation_skipped: newSkipped.join(","),
            },
          },
        });
      }
      setSelectedStep(nextStep);
    }
  };

  const handleSkip = async () => {
    const newSkipped = Array.from(new Set([...skipped, step]));
    const newCompleted = completed.filter((s) => s !== step);
    setSkipped(newSkipped);
    setCompleted(newCompleted);

    if (isLastAction(step, true)) {
      await finishOrientation();
    } else {
      const nextStep = Math.min(5, step + 1);
      await put("/orientation", { step: nextStep, skipped: newSkipped });
      if (session) {
        setSession({
          ...session,
          user: {
            ...session.user,
            profile: {
              ...session.user.profile,
              orientation_step: String(nextStep),
              orientation_skipped: newSkipped.join(","),
            },
          },
        });
      }
      setSelectedStep(nextStep);
    }
  };

  const isFinalStep = isLastAction(step, false);

  return (
    <Panel title={`${step} / 5 · ${current.title}`}>
      <div
        className="onboarding-steps"
        style={{
          gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
          marginBottom: "16px",
        }}
      >
        {steps.map((s) => {
          const isComp = completed.includes(s.number);
          const isSkip = skipped.includes(s.number);
          const isCurr = step === s.number;
          return (
            <button
              key={s.number}
              type="button"
              className={isCurr ? "step-current" : ""}
              onClick={() => setSelectedStep(s.number)}
            >
              <span>
                {isComp ? (
                  <CheckCircle2 size={16} />
                ) : (
                  String(s.number).padStart(2, "0")
                )}
              </span>
              <strong>{s.title}</strong>
              <Status
                value={
                  isComp
                    ? "completed"
                    : isSkip
                      ? "skipped"
                      : isCurr
                        ? "active"
                        : "pending"
                }
              />
            </button>
          );
        })}
      </div>
      <p>{current.description}</p>
      <div className="work-actions">
        <Link className="button button-outline" to={current.href}>
          {t("Review this area", "यह भाग देखें")}
        </Link>
        <ActionButton action={handleContinue}>
          {isFinalStep
            ? t("Complete & go to overview", "पूरा करें और अवलोकन पर जाएँ")
            : t("Save and continue", "सहेजें और जारी रखें")}
        </ActionButton>
        <ActionButton action={handleSkip}>
          {isFinalStep
            ? t("Skip & go to overview", "छोड़ें और अवलोकन पर जाएँ")
            : t("Skip step", "चरण छोड़ें")}
        </ActionButton>
      </div>
      <p className="work-note">
        {t(
          "Progress is saved to your account. You can leave and return.",
          "प्रगति आपके खाते में सुरक्षित है। आप बाद में लौट सकते हैं।",
        )}
      </p>
    </Panel>
  );
}

export function AttentionPage() {
  const { departments } = useCatalog();
  const { t } = usePreferences();
  const w = useWords();
  const [params] = useSearchParams();
  const [department, setDepartment] = useState(params.get("department") || "");
  const data = useQuery({
    queryKey: ["workspace-context", department],
    queryFn: () =>
      api<Context>(
        `/workspace/context${search({ department_id: department })}`,
      ),
  });
  return (
    <>
      <PageTitle
        title={t("Needs attention", "ध्यान आवश्यक")}
        description={t(
          "Immediate safety first, then approvals, conflicts, blocked work and overdue responsibilities.",
          "पहले तत्काल सुरक्षा, फिर मंज़ूरी, विरोधाभास, रुके कार्य और समय सीमा पार जिम्मेदारियाँ।",
        )}
      />
      <label className="form-field">
        {w("Department")}
        <select
          value={department}
          onChange={(event) => setDepartment(event.target.value)}
        >
          <option value="">{w("All")}</option>
          {departments.data?.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </select>
      </label>
      <Panel>
        <When loading={data.isLoading} error={data.error}>
          {!data.data?.attention.length ? (
            <Empty>
              {t(
                "No outstanding exceptions in this scope.",
                "इस क्षेत्र में ध्यान देने योग्य लंबित विषय नहीं हैं।",
              )}
            </Empty>
          ) : (
            data.data.attention.map((item) => (
              <Link
                className="work-list-row"
                key={`${item.kind}-${item.id}`}
                to={item.href}
              >
                <div>
                  <h3>{item.title}</h3>
                  <p>{item.reason}</p>
                  <small>
                    {
                      departments.data?.find((d) => d.id === item.department_id)
                        ?.name
                    }{" "}
                    · {item.responsible || ""} · {formatDate(item.created_at)}
                  </small>
                </div>
                <div className="work-tags">
                  {item.rank <= 1 && <Status value="critical" />}
                  <Status value={item.status} />
                  <span className="text-link">{w("View details")} →</span>
                </div>
              </Link>
            ))
          )}
        </When>
      </Panel>
    </>
  );
}

type DepartmentDetail = Department & {
  teams: Team[];
  people: {
    id: string;
    name: string;
    role: string;
    active: boolean;
    membership: Membership;
  }[];
  activity: History[];
};
export function DepartmentDetailPage() {
  const { id } = useParams();
  const { t } = usePreferences();
  const w = useWords();
  const data = useQuery({
    queryKey: ["department-overview", id],
    queryFn: () => api<DepartmentDetail>(`/departments/${id}/overview`),
  });
  const item = data.data;
  return (
    <>
      <PageTitle title={item?.name || "Department"} />
      <When loading={data.isLoading} error={data.error}>
        {item && (
          <>
            <Panel>
              <p>{item.description}</p>
              <Status value={item.active ? "Active" : "Inactive"} />
              <div className="work-actions">
                <Link
                  className="button button-outline"
                  to={`/workspace/analytics?department=${id}`}
                >
                  {w("Analytics")}
                </Link>
                <Link
                  className="button button-outline"
                  to={`/workspace/attention?department=${id}`}
                >
                  {t("Needs attention", "ध्यान आवश्यक")}
                </Link>
              </div>
            </Panel>
            <div className="work-two-column">
              <Panel title="Teams">
                {item.teams.map((team) => (
                  <div className="work-list-row" key={team.id}>
                    <div>
                      <Link
                        className="text-link"
                        to={`/workspace/teams/${team.id}`}
                      >
                        <strong>{team.name}</strong>
                      </Link>
                      <p>{team.description}</p>
                    </div>
                    <Status value={team.active ? "Active" : "Inactive"} />
                  </div>
                ))}
              </Panel>
              <Panel title="Supervisors">
                {item.people
                  .filter((person) => person.role === "supervisor")
                  .map((person) => (
                    <div className="work-list-row" key={person.id}>
                      <div>
                        <strong>{person.name}</strong>
                        <p>
                          {person.membership.permissions.map(w).join(" · ")}
                        </p>
                      </div>
                      <Status
                        value={
                          person.membership.primary
                            ? "Primary"
                            : person.membership.backup
                              ? "Backup"
                              : "Active"
                        }
                      />
                    </div>
                  ))}
              </Panel>
            </div>
            <Panel title="Workforce">
              {item.people
                .filter((person) => person.role === "worker")
                .map((person) => (
                  <Link
                    className="work-list-row"
                    key={person.id}
                    to={`/workspace/workforce/${person.id}`}
                  >
                    <strong>{person.name}</strong>
                    <Status value={person.active ? "Active" : "Inactive"} />
                  </Link>
                ))}
            </Panel>
            <Panel title="History">
              {!item.activity.length ? (
                <Empty />
              ) : (
                item.activity.map((event) => (
                  <div className="work-list-row" key={event.id}>
                    <strong>{event.action}</strong>
                    <span>{formatDate(event.created_at)}</span>
                  </div>
                ))
              )}
            </Panel>
          </>
        )}
      </When>
    </>
  );
}

export function TeamDetailPage() {
  const { id } = useParams();
  const { t } = usePreferences();
  const w = useWords();
  const { departments } = useCatalog();
  const data = useQuery({
    queryKey: ["team-overview", id],
    queryFn: () =>
      api<Team & { people: Person[]; supervisors: Person[]; tasks: Task[] }>(
        `/teams/${id}/overview`,
      ),
  });
  const item = data.data;
  return (
    <>
      <PageTitle title={item?.name || "Team"} />
      <When loading={data.isLoading} error={data.error}>
        {item && (
          <>
            <Panel>
              <p>{item.description}</p>
              <Status value={item.active ? "Active" : "Inactive"} />
              <p>
                <Link
                  className="text-link"
                  to={`/workspace/departments/${item.department_id}`}
                >
                  {
                    departments.data?.find((d) => d.id === item.department_id)
                      ?.name
                  }
                </Link>
              </p>
              <Link className="text-link" to="/workspace/workforce">
                {t("Manage team memberships", "टीम सदस्यता प्रबंधित करें")} →
              </Link>
            </Panel>
            <div className="work-two-column">
              <Panel title="Workforce">
                {!item.people.length ? (
                  <Empty />
                ) : (
                  item.people.map((p) => (
                    <Link
                      className="work-list-row"
                      key={p.id}
                      to={`/workspace/workforce/${p.id}`}
                    >
                      <div>
                        <strong>{p.name}</strong>
                        <p>{p.employee_code}</p>
                      </div>
                      <Status value={p.active ? "Active" : "Inactive"} />
                    </Link>
                  ))
                )}
              </Panel>
              <Panel title="Supervisors">
                {!item.supervisors.length ? (
                  <Empty />
                ) : (
                  item.supervisors.map((p) => (
                    <div className="work-list-row" key={p.id}>
                      <strong>{p.name}</strong>
                      <Status value={p.active ? "Active" : "Inactive"} />
                    </div>
                  ))
                )}
              </Panel>
            </div>
            <Panel title="Tasks">
              {!item.tasks.length ? (
                <Empty />
              ) : (
                item.tasks.map((task) => (
                  <Link
                    className="work-list-row"
                    key={task.id}
                    to={`/workspace/tasks/${task.id}`}
                  >
                    <div>
                      <strong>{task.title}</strong>
                      <p>
                        {task.deadline
                          ? formatDate(task.deadline)
                          : w("No deadline")}
                      </p>
                    </div>
                    <Status value={task.status} />
                  </Link>
                ))
              )}
            </Panel>
          </>
        )}
      </When>
    </>
  );
}

export function SupervisorDetailPage() {
  const { id } = useParams();
  const { t } = usePreferences();
  const w = useWords();
  const { departments, shifts } = useCatalog();
  const data = useQuery({
    queryKey: ["supervisor-overview", id],
    queryFn: () =>
      api<
        Person & {
          shifts: ShiftAssignment[];
          responsibilities: {
            id: string;
            department_id: string;
            machine: string;
            area: string;
            category: string;
          }[];
          activity: History[];
        }
      >(`/supervisors/${id}/overview`),
  });
  const item = data.data;
  return (
    <>
      <PageTitle title={item?.name || "Supervisor"}>
        <Link className="button button-outline" to="/workspace/supervisors">
          {t("Manage access", "अनुमतियाँ प्रबंधित करें")}
        </Link>
      </PageTitle>
      <When loading={data.isLoading} error={data.error}>
        {item && (
          <>
            <Panel>
              <dl className="work-definition">
                <div>
                  <dt>{w("Email")}</dt>
                  <dd>{item.email}</dd>
                </div>
                <div>
                  <dt>{t("Account ID", "खाता आईडी")}</dt>
                  <dd>{item.id}</dd>
                </div>
                <div>
                  <dt>{w("Contact number")}</dt>
                  <dd>{item.phone || "—"}</dd>
                </div>
              </dl>
              <Status
                value={
                  item.active
                    ? "Active"
                    : item.verified
                      ? "Inactive"
                      : "Pending"
                }
              />
            </Panel>
            <Panel title="Departments">
              {item.departments?.map((m) => (
                <div className="work-list-row" key={m.id}>
                  <div>
                    <Link
                      className="text-link"
                      to={`/workspace/departments/${m.department_id}`}
                    >
                      {
                        departments.data?.find((d) => d.id === m.department_id)
                          ?.name
                      }
                    </Link>
                    <p>{m.permissions.map(w).join(" · ")}</p>
                  </div>
                  <Status
                    value={
                      m.primary ? "Primary" : m.backup ? "Backup" : "Active"
                    }
                  />
                </div>
              ))}
            </Panel>
            <div className="work-two-column">
              <Panel title="Shifts">
                {!item.shifts.length ? (
                  <Empty />
                ) : (
                  item.shifts.map((a) => (
                    <div className="work-list-row" key={a.id}>
                      <div>
                        <strong>
                          {shifts.data?.find((s) => s.id === a.shift_id)?.name}
                        </strong>
                        <p>
                          {a.starts_on} — {a.ends_on || t("Ongoing", "जारी")}
                        </p>
                      </div>
                      <Status value={a.active ? "Active" : "Inactive"} />
                    </div>
                  ))
                )}
              </Panel>
              <Panel title={t("Responsibilities", "जिम्मेदारियाँ")}>
                {!item.responsibilities.length ? (
                  <Empty />
                ) : (
                  item.responsibilities.map((r) => (
                    <div className="work-list-row" key={r.id}>
                      <div>
                        <strong>
                          {
                            departments.data?.find(
                              (d) => d.id === r.department_id,
                            )?.name
                          }
                        </strong>
                        <p>
                          {[r.machine, r.area, r.category]
                            .filter(Boolean)
                            .join(" · ") ||
                            t("Department coverage", "विभाग की जिम्मेदारी")}
                        </p>
                      </div>
                    </div>
                  ))
                )}
                <Link className="text-link" to="/workspace/policies">
                  {t(
                    "Review responsibility mapping",
                    "जिम्मेदारी मानचित्र देखें",
                  )}{" "}
                  →
                </Link>
              </Panel>
            </div>
            <Panel title="History">
              {!item.activity.length ? (
                <Empty />
              ) : (
                item.activity.map((event) => (
                  <div className="work-list-row" key={event.id}>
                    <strong>{event.action}</strong>
                    <span>{formatDate(event.created_at)}</span>
                  </div>
                ))
              )}
            </Panel>
          </>
        )}
      </When>
    </>
  );
}
