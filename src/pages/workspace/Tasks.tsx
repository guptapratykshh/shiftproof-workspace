import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { CalendarDays, Plus } from "lucide-react";
import { useCatalog } from "../../components/workspace/Workspace";
import {
  ActionButton,
  Empty,
  ErrorNotice,
  FieldsForm,
  FilterBar,
  Modal,
  PageTitle,
  Panel,
  Status,
  When,
  commaList,
  formatDate,
  iso,
  list,
  nullable,
  options,
  str,
  useWords,
  type FieldSpec,
} from "../../components/workspace/UI";
import { api, evidenceUrl, post, put, remove, search } from "../../lib/api";
import { useSession } from "../../lib/session";
import { usePreferences } from "../../lib/preferences";
import type { Asset, Paged, Task } from "../../lib/types";

export const priorities = ["normal", "important", "urgent", "critical"];
export const taskStatuses = [
  "assigned",
  "accepted",
  "in_progress",
  "blocked",
  "completed",
  "verified",
  "closed",
];
export function TaskForm({
  onSaved,
  sourceReportId,
  departmentId,
  endpoint = "/tasks",
  template = false,
  critical = false,
}: {
  onSaved: () => void;
  sourceReportId?: string;
  departmentId?: string;
  endpoint?: string;
  template?: boolean;
  critical?: boolean;
}) {
  const { departments, teams, shifts, workers } = useCatalog();
  const { t } = usePreferences();
  const w = useWords();
  const [assignment, setAssignment] = useState("individual");
  const tasks = useQuery({
    queryKey: ["tasks", "dependencies"],
    queryFn: () => api<Paged<Task>>("/tasks?limit=200"),
  });
  const fields: FieldSpec[] = [
    { name: "title", label: "Title", required: true, wide: true },
    { name: "description", label: "Description", type: "textarea" },
    { name: "instructions", label: "Instructions", type: "textarea" },
    {
      name: "department_id",
      label: "Department",
      type: "select",
      required: true,
      options: options(departments.data?.filter((d) => d.active)),
      defaultValue: departmentId,
    },
    assignment === "individual"
      ? {
          name: "worker_id",
          label: "Worker",
          type: "select",
          required: true,
          options: options(workers.data?.items.filter((p) => p.active)),
        }
      : {
          name: "team_id",
          label: "Team",
          type: "select",
          required: true,
          options: options(teams.data?.filter((team) => team.active)),
        },
    ...(assignment === "team"
      ? [
          {
            name: "lead_id",
            label: "Team lead",
            type: "select",
            options: options(workers.data?.items.filter((p) => p.active)),
          } as FieldSpec,
        ]
      : []),
    {
      name: "shift_id",
      label: "Shift",
      type: "select",
      options: options(shifts.data?.filter((s) => s.active)),
    },
    { name: "deadline", label: "Deadline", type: "datetime-local" },
    {
      name: "priority",
      label: "Priority",
      type: "select",
      options: priorities.map((value) => ({ value, label: value })),
      hint: t(
        "Optional. Critical work always needs supervisor approval.",
        "वैकल्पिक। गंभीर कार्य के लिए पर्यवेक्षक की मंज़ूरी आवश्यक है।",
      ),
    },
    {
      name: "category",
      label: "Category",
      type: "select",
      defaultValue: "general",
      options: [
        "general",
        "progress",
        "safety",
        "quality",
        "equipment",
        "maintenance",
        "materials",
      ].map((value) => ({ value, label: value })),
    },
    {
      name: "required_skills",
      label: "Required skills",
      hint: t(
        "Comma-separated. Only qualified, available workers can be assigned.",
        "कॉमा से अलग करें। केवल योग्य, उपलब्ध कर्मचारियों को कार्य सौंप सकते हैं।",
      ),
    },
    {
      name: "depends_on",
      label: t("Dependencies", "निर्भर कार्य"),
      type: "multi",
      options: options(tasks.data?.items),
    },
    {
      name: "critical",
      label: "Critical",
      type: "checkbox",
      defaultValue: critical,
    },
    {
      name: "verification_required",
      label: "Review required",
      type: "checkbox",
    },
    ...(template
      ? ([
          {
            name: "auto_allocate",
            label: t(
              "Automatically allocate approved routine work",
              "मंज़ूर नियमित कार्य अपने आप सौंपें",
            ),
            type: "checkbox",
          },
          {
            name: "recurrence_minutes",
            label: "Recurrence in minutes",
            type: "number",
            min: 15,
            max: 525600,
          },
          { name: "next_run", label: "First run", type: "datetime-local" },
        ] as FieldSpec[])
      : []),
  ];
  return (
    <div className="work-stack">
      <label className="form-field">
        {w("Assignment type")}
        <select
          value={assignment}
          onChange={(event) => setAssignment(event.target.value)}
        >
          <option value="individual">{w("Individual")}</option>
          <option value="team">{w("Shared team task")}</option>
        </select>
      </label>
      <FieldsForm
        key={assignment}
        fields={fields}
        submitLabel={template ? "Save" : "Create task"}
        onSubmit={(values) => {
          const payload = {
            title: values.title,
            description: values.description,
            instructions: values.instructions,
            department_id: values.department_id,
            worker_id: nullable(values.worker_id),
            team_id: nullable(values.team_id),
            lead_id: nullable(values.lead_id),
            assignment_type: assignment,
            shift_id: nullable(values.shift_id),
            deadline: iso(values.deadline),
            priority: nullable(values.priority),
            category: str(values.category) || "general",
            required_skills: commaList(values.required_skills),
            depends_on: list(values.depends_on),
            critical: values.critical,
            verification_required: values.verification_required,
            source_report_id: sourceReportId || null,
          };
          return post(
            endpoint,
            template
              ? {
                  task: payload,
                  auto_allocate: !!values.auto_allocate,
                  recurrence_minutes: values.recurrence_minutes
                    ? Number(values.recurrence_minutes)
                    : null,
                  next_run: iso(values.next_run),
                }
              : payload,
          );
        }}
        onSuccess={onSaved}
      >
        {assignment === "individual" && <AllocationHelper />}
      </FieldsForm>
    </div>
  );
}

function AllocationHelper() {
  const { t } = usePreferences();
  const [suggestions, setSuggestions] = useState<
    { worker_id: string; name: string; open_tasks: number }[] | null
  >(null);
  const [error, setError] = useState<unknown>(null);
  return (
    <div className="work-stack">
      <button
        type="button"
        className="button button-outline"
        onClick={async (event) => {
          const form = event.currentTarget.form!;
          const values = new FormData(form);
          setError(null);
          try {
            const result = await api<{
              items: NonNullable<typeof suggestions>;
            }>(
              `/allocation-suggestions${search({ department_id: String(values.get("department_id") || ""), required_skills: String(values.get("required_skills") || ""), shift_id: String(values.get("shift_id") || "") })}`,
            );
            setSuggestions(result.items);
          } catch (cause) {
            setError(cause);
          }
        }}
      >
        {t(
          "Find qualified, available workers",
          "योग्य और उपलब्ध कर्मचारी खोजें",
        )}
      </button>
      {!!error && <ErrorNotice error={error} />}
      {suggestions && (
        <>
          <p className="work-note">
            {t(
              "Ordered by open workload, then longest time since assignment. You confirm the final assignment.",
              "खुले कार्यभार और पिछला कार्य सौंपे जाने के समय से क्रमबद्ध। अंतिम चयन की पुष्टि आप करेंगे।",
            )}
          </p>
          {!suggestions.length ? (
            <Empty />
          ) : (
            suggestions.map((person) => (
              <button
                type="button"
                className="button button-outline"
                key={person.worker_id}
                onClick={(event) => {
                  const select = event.currentTarget.form?.elements.namedItem(
                    "worker_id",
                  ) as HTMLSelectElement | null;
                  if (select) {
                    select.value = person.worker_id;
                    select.dispatchEvent(
                      new Event("change", { bubbles: true }),
                    );
                    select.focus();
                  }
                }}
              >
                {person.name} · {person.open_tasks}{" "}
                {t("open tasks", "खुले कार्य")}
              </button>
            ))
          )}
        </>
      )}
    </div>
  );
}

export function TasksPage() {
  const session = useSession((state) => state.session)!;
  const management = session.user.role !== "worker";
  const { departments, teams } = useCatalog();
  const { t } = usePreferences();
  const w = useWords();
  const [filter, setFilter] = useState({
    department_id: "",
    status: "",
    priority: "",
    q: "",
    team_id: "",
    worker_id: "",
    category: "",
    due_before: "",
  });
  const [page, setPage] = useState(1);
  const [creating, setCreating] = useState(false);
  const [calendar, setCalendar] = useState(false);
  const [board, setBoard] = useState(false);
  const [month, setMonth] = useState(new Date().toISOString().slice(0, 7));
  const [templatesOpen, setTemplatesOpen] = useState(false);
  const [templateCreate, setTemplateCreate] = useState(false);
  const [selection, setSelection] = useState<string[]>([]);
  const [bulk, setBulk] = useState(false);
  const tasks = useQuery({
    queryKey: ["tasks", filter, page, calendar, board],
    queryFn: () =>
      api<Paged<Task>>(
        `/tasks${search({ ...filter, page: calendar || board ? 1 : page, limit: calendar || board ? 200 : 25 })}`,
      ),
  });
  const { workers } = useCatalog();
  const templates = useQuery({
    queryKey: ["task-templates"],
    queryFn: () =>
      api<
        {
          id: string;
          title: string;
          active: boolean;
          recurrence_minutes: number | null;
          next_run: string;
        }[]
      >("/task-templates"),
    enabled: management,
  });
  const first = new Date(`${month}-01T12:00:00`);
  const days = new Date(first.getFullYear(), first.getMonth() + 1, 0).getDate();
  return (
    <>
      <PageTitle
        title="Tasks"
        description={
          management
            ? t(
                "Clear ownership, visible progress, and approval where it matters.",
                "स्पष्ट जिम्मेदारी, दिखाई देने वाली प्रगति और आवश्यक मंज़ूरी।",
              )
            : t(
                "Accept your work, keep its progress current, and flag anything blocking you.",
                "कार्य स्वीकारें, प्रगति अपडेट रखें और रुकावट बताएँ।",
              )
        }
      >
        <button
          className="button button-outline"
          onClick={() => {
            setCalendar(!calendar);
            setBoard(false);
          }}
        >
          <CalendarDays size={17} />
          {w(calendar ? "View list" : "View calendar")}
        </button>
        {management && (
          <>
            <button
              className="button button-outline"
              onClick={() => setTemplatesOpen(true)}
            >
              {t("Templates", "टेम्पलेट")}
            </button>
            <button
              className="button button-primary"
              onClick={() => setCreating(true)}
            >
              <Plus size={17} />
              {w("Create task")}
            </button>
          </>
        )}
        <button
          className="button button-outline"
          onClick={() => {
            setBoard(!board);
            setCalendar(false);
          }}
        >
          {board
            ? t("View list", "सूची देखें")
            : t("View board", "बोर्ड देखें")}
        </button>
      </PageTitle>
      <FilterBar activeCount={Object.values(filter).filter(Boolean).length}>
        <label>
          {w("Search by name")}
          <input
            value={filter.q}
            onChange={(event) => {
              setFilter({ ...filter, q: event.target.value });
              setPage(1);
            }}
          />
        </label>
        <label>
          {w("Department")}
          <select
            value={filter.department_id}
            onChange={(event) => {
              setFilter({ ...filter, department_id: event.target.value });
              setPage(1);
            }}
          >
            <option value="">{w("All")}</option>
            {departments.data?.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </label>
        {(
          [
            { key: "team_id", label: "Team", items: teams.data },
            ...(management
              ? [
                  {
                    key: "worker_id" as const,
                    label: "Worker",
                    items: workers.data?.items,
                  },
                ]
              : []),
          ] as const
        ).map((field) => (
          <label key={field.key}>
            {w(field.label)}
            <select
              value={filter[field.key]}
              onChange={(event) => {
                setFilter({ ...filter, [field.key]: event.target.value });
                setPage(1);
              }}
            >
              <option value="">{w("All")}</option>
              {field.items?.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.name}
                </option>
              ))}
            </select>
          </label>
        ))}
        <label>
          {w("Category")}
          <select
            value={filter.category}
            onChange={(event) => {
              setFilter({ ...filter, category: event.target.value });
              setPage(1);
            }}
          >
            <option value="">{w("All")}</option>
            {[
              "general",
              "progress",
              "safety",
              "quality",
              "equipment",
              "maintenance",
              "materials",
            ].map((value) => (
              <option key={value} value={value}>
                {w(value)}
              </option>
            ))}
          </select>
        </label>
        <label>
          {t("Due on or before", "इस तिथि तक देय")}
          <input
            type="date"
            value={filter.due_before}
            onChange={(event) => {
              setFilter({ ...filter, due_before: event.target.value });
              setPage(1);
            }}
          />
        </label>
        {(["status", "priority"] as const).map((key) => (
          <label key={key}>
            {w(key === "status" ? "Status" : "Priority")}
            <select
              value={filter[key]}
              onChange={(event) => {
                setFilter({ ...filter, [key]: event.target.value });
                setPage(1);
              }}
            >
              <option value="">{w("All")}</option>
              {(key === "status" ? taskStatuses : priorities).map((value) => (
                <option key={value} value={value}>
                  {w(value)}
                </option>
              ))}
            </select>
          </label>
        ))}
      </FilterBar>
      {selection.length > 0 && (
        <div className="selection-bar">
          <span>
            {selection.length} {t("selected tasks", "चुने गए कार्य")}
          </span>
          <button
            className="button button-outline"
            onClick={() => setBulk(true)}
          >
            {w("Reassign")}
          </button>
        </div>
      )}
      <Panel>
        <When loading={tasks.isLoading} error={tasks.error}>
          {!tasks.data?.items.length ? (
            <Empty>
              {t(
                "Tasks appear here when responsibility is assigned.",
                "जिम्मेदारी सौंपे जाने पर कार्य यहाँ दिखेंगे।",
              )}
            </Empty>
          ) : board ? (
            <>
              <p className="work-note">
                {t(
                  "Board shows up to 200 tasks in the selected scope.",
                  "बोर्ड चुने क्षेत्र के अधिकतम 200 कार्य दिखाता है।",
                )}
              </p>
              <div className="task-board">
                {taskStatuses.map((status) => (
                  <section key={status}>
                    <h3>{w(status)}</h3>
                    {tasks.data.items
                      .filter((task) => task.status === status)
                      .map((task) => (
                        <Link
                          className="task-board-card"
                          to={`/workspace/tasks/${task.id}`}
                          key={task.id}
                        >
                          <strong>{task.title}</strong>
                          {task.priority && <Status value={task.priority} />}
                          <small>
                            {formatDate(
                              task.deadline,
                              session.organization.timezone,
                            )}
                          </small>
                        </Link>
                      ))}
                  </section>
                ))}
              </div>
            </>
          ) : calendar ? (
            <>
              <label className="form-field">
                {t("Month", "महीना")}
                <input
                  type="month"
                  value={month}
                  onChange={(event) => setMonth(event.target.value)}
                />
              </label>
              {tasks.data.total > 200 && (
                <p className="work-warning">
                  {t(
                    "Showing the latest 200 tasks. Narrow the filters to review a smaller set.",
                    "नवीनतम 200 कार्य दिख रहे हैं। फ़िल्टर से सूची सीमित करें।",
                  )}
                </p>
              )}
              <div className="task-calendar">
                {Array.from({ length: days }, (_, index) => {
                  const date = `${month}-${String(index + 1).padStart(2, "0")}`;
                  const dayTasks = tasks.data!.items.filter(
                    (task) =>
                      task.deadline &&
                      new Intl.DateTimeFormat("en-CA", {
                        timeZone: session.organization.timezone,
                      }).format(new Date(task.deadline)) === date,
                  );
                  return (
                    <div className="calendar-day" key={date}>
                      <strong>{index + 1}</strong>
                      {dayTasks.map((task) => (
                        <Link to={`/workspace/tasks/${task.id}`} key={task.id}>
                          <span>{task.title}</span>
                          <Status value={task.status} />
                        </Link>
                      ))}
                    </div>
                  );
                })}
              </div>
            </>
          ) : (
            tasks.data.items.map((task) => (
              <div className="task-row" key={task.id}>
                {management &&
                  task.assignment_type === "individual" &&
                  !["closed", "verified"].includes(task.status) && (
                    <input
                      type="checkbox"
                      aria-label={`${t("Select", "चुनें")} ${task.title}`}
                      checked={selection.includes(task.id)}
                      onChange={(event) =>
                        setSelection(
                          event.target.checked
                            ? [...selection, task.id]
                            : selection.filter((id) => id !== task.id),
                        )
                      }
                    />
                  )}
                <Link
                  to={`/workspace/tasks/${task.id}`}
                  className="task-row-main"
                >
                  <div>
                    <h3>{task.title}</h3>
                    <p>
                      {
                        departments.data?.find(
                          (d) => d.id === task.department_id,
                        )?.name
                      }{" "}
                      ·{" "}
                      {w(
                        task.assignment_type === "team"
                          ? "Shared team task"
                          : "Individual",
                      )}
                    </p>
                    <div className="work-tags">
                      <Status value={task.status} />
                      {task.priority && <Status value={task.priority} />}
                      {task.critical && (
                        <span className="work-warning">
                          {w("Review required before closure")}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="task-deadline">
                    <small>{w("Deadline")}</small>
                    <span>
                      {formatDate(task.deadline, session.organization.timezone)}
                    </span>
                    {task.deadline &&
                      Date.parse(task.deadline) < Date.now() &&
                      task.status !== "closed" && <Status value="Overdue" />}
                  </div>
                </Link>
              </div>
            ))
          )}
        </When>
      </Panel>
      {!calendar && !board && (
        <div className="pagination">
          <button
            className="button button-outline"
            disabled={page === 1}
            onClick={() => setPage(page - 1)}
          >
            {w("Previous page")}
          </button>
          <span>
            {page} / {Math.max(1, Math.ceil((tasks.data?.total || 0) / 25))}
          </span>
          <button
            className="button button-outline"
            disabled={page * 25 >= (tasks.data?.total || 0)}
            onClick={() => setPage(page + 1)}
          >
            {w("Next page")}
          </button>
        </div>
      )}
      {creating && (
        <Modal title="Create task" onClose={() => setCreating(false)}>
          <TaskForm onSaved={() => setCreating(false)} />
        </Modal>
      )}
      {templatesOpen && (
        <Modal
          title={t("Task templates", "कार्य टेम्पलेट")}
          onClose={() => setTemplatesOpen(false)}
        >
          <div className="work-stack">
            <button
              className="button button-primary"
              onClick={() => {
                setTemplatesOpen(false);
                setTemplateCreate(true);
              }}
            >
              {w("Create")}
            </button>
            {!templates.data?.length ? (
              <Empty />
            ) : (
              templates.data.map((item) => (
                <div className="work-list-row" key={item.id}>
                  <div>
                    <strong>{item.title}</strong>
                    <p>
                      {item.recurrence_minutes
                        ? `${item.recurrence_minutes} ${t("minutes", "मिनट")}`
                        : t("Use when needed", "ज़रूरत पर उपयोग करें")}
                    </p>
                    <Status value={item.active ? "Active" : "Inactive"} />
                  </div>
                  <div className="work-actions">
                    <ActionButton
                      action={() => post(`/task-templates/${item.id}/apply`)}
                    >
                      {w("Create task")}
                    </ActionButton>
                    {item.active && (
                      <ActionButton
                        action={() => remove(`/task-templates/${item.id}`)}
                      >
                        {t("Stop recurrence", "दोहराव रोकें")}
                      </ActionButton>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </Modal>
      )}
      {templateCreate && (
        <Modal
          title={t("Create task template", "कार्य टेम्पलेट बनाएँ")}
          onClose={() => setTemplateCreate(false)}
        >
          <TaskForm
            endpoint="/task-templates"
            template
            onSaved={() => setTemplateCreate(false)}
          />
        </Modal>
      )}
      {bulk && (
        <Modal title="Reassign" onClose={() => setBulk(false)}>
          <FieldsForm
            fields={[
              {
                name: "worker_id",
                label: "Worker",
                type: "select",
                required: true,
                options: options(workers.data?.items.filter((p) => p.active)),
              },
              {
                name: "reason",
                label: "Reason",
                type: "textarea",
                required: true,
              },
            ]}
            onSubmit={(values) =>
              post("/task-reassignments", { ...values, task_ids: selection })
            }
            onSuccess={() => {
              setSelection([]);
              setBulk(false);
            }}
          />
        </Modal>
      )}
    </>
  );
}

export function TaskDetailPage() {
  const { id } = useParams();
  const session = useSession((state) => state.session)!;
  const worker = session.user.role === "worker";
  const { workers, teams, departments } = useCatalog();
  const { t } = usePreferences();
  const w = useWords();
  const task = useQuery({
    queryKey: ["task", id],
    queryFn: () => api<Task>(`/tasks/${id}`),
  });
  const [modal, setModal] = useState<string | null>(null);
  const attachments = useQuery({
    queryKey: ["task-evidence", id],
    queryFn: () => api<Asset[]>(`/tasks/${id}/evidence`),
  });
  const [attachmentError, setAttachmentError] = useState<unknown>(null);
  const item = task.data;
  const next: Record<string, string[]> = {
    assigned: ["accept", "block"],
    accepted: ["start", "block"],
    in_progress: ["complete", "block"],
    blocked: ["resume"],
    completed: worker ? [] : ["verify", "reject"],
    verified: worker ? [] : ["close"],
    closed: [],
  };
  const actionLabel: Record<string, string> = {
    accept: "Accept",
    start: "Start",
    complete: "Complete",
    block: "Block",
    resume: "Resume",
    verify: "Verify",
    reject: "Reject",
    close: "Close",
  };
  return (
    <>
      <PageTitle title={item?.title || "Tasks"} />
      <When loading={task.isLoading} error={task.error}>
        {item && (
          <>
            <Panel>
              <div className="work-tags section-actions">
                <Status value={item.status} />
                {item.priority && <Status value={item.priority} />}
                {item.verification_required && (
                  <span className="work-warning">
                    {w("Review required before closure")}
                  </span>
                )}
              </div>
              <p className="work-copy">
                {item.description ||
                  t("No additional description.", "अतिरिक्त विवरण नहीं है।")}
              </p>
              {item.instructions && (
                <div className="instruction-box">
                  <h3>{w("Instructions")}</h3>
                  <p>{item.instructions}</p>
                </div>
              )}
              <dl className="work-definition">
                <div>
                  <dt>{w("Department")}</dt>
                  <dd>
                    {
                      departments.data?.find((d) => d.id === item.department_id)
                        ?.name
                    }
                  </dd>
                </div>
                <div>
                  <dt>{w("Deadline")}</dt>
                  <dd>
                    {formatDate(item.deadline, session.organization.timezone)}
                  </dd>
                </div>
                <div>
                  <dt>{w("Required skills")}</dt>
                  <dd>
                    {item.required_skills.join(", ") ||
                      t("None required", "कोई आवश्यक नहीं")}
                  </dd>
                </div>
                <div>
                  <dt>{w("Assignment type")}</dt>
                  <dd>
                    {w(
                      item.assignment_type === "team"
                        ? "Shared team task"
                        : "Individual",
                    )}
                  </dd>
                </div>
              </dl>
              {item.blocked_reason && (
                <p className="work-warning">{item.blocked_reason}</p>
              )}
              <div className="work-actions">
                {(next[item.status] || []).map((action) =>
                  ["block", "reject", "verify"].includes(action) ? (
                    <button
                      className="button button-primary"
                      key={action}
                      onClick={() => setModal(action)}
                    >
                      {w(actionLabel[action])}
                    </button>
                  ) : (
                    <ActionButton
                      className="button button-primary"
                      key={action}
                      action={() =>
                        post(`/tasks/${id}/actions`, {
                          action,
                          version: item.version,
                        })
                      }
                    >
                      {w(actionLabel[action])}
                    </ActionButton>
                  ),
                )}
                {!worker && !["verified", "closed"].includes(item.status) && (
                  <>
                    <button
                      className="button button-outline"
                      onClick={() => setModal("reassign")}
                    >
                      {w("Reassign")}
                    </button>
                    <button
                      className="button button-outline"
                      onClick={() => setModal("edit")}
                    >
                      {t("Edit task", "कार्य बदलें")}
                    </button>
                  </>
                )}
                <Link
                  className="button button-outline"
                  to={`/workspace/record?task=${item.id}&department=${item.department_id}`}
                >
                  {w("New report")}
                </Link>
              </div>
            </Panel>
            <div className="work-two-column">
              <Panel title="Responsibility history">
                {item.assignments?.map((assignment) => (
                  <div className="work-list-row" key={assignment.id}>
                    <div>
                      <strong>
                        {assignment.user_id
                          ? workers.data?.items.find(
                              (p) => p.id === assignment.user_id,
                            )?.name || t("Worker", "कर्मचारी")
                          : teams.data?.find(
                              (team) => team.id === assignment.team_id,
                            )?.name || t("Team", "टीम")}
                      </strong>
                      <p>{assignment.reason}</p>
                    </div>
                    <Status
                      value={assignment.ended_at ? "Previous" : "Active"}
                    />
                  </div>
                ))}
              </Panel>
              <Panel title="Comments">
                {!item.comments?.length ? (
                  <Empty />
                ) : (
                  item.comments.map((comment) => (
                    <div className="comment" key={comment.id}>
                      {comment.internal && <Status value="Internal note" />}
                      <p>{comment.text}</p>
                      <small>
                        {formatDate(
                          comment.created_at,
                          session.organization.timezone,
                        )}
                      </small>
                    </div>
                  ))
                )}
                <button
                  className="button button-outline"
                  onClick={() => setModal("comment")}
                >
                  {w("Add comment")}
                </button>
              </Panel>
            </div>
            <Panel title="Related reports">
              {!item.reports?.length ? (
                <Empty />
              ) : (
                item.reports.map((report) => (
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
            <Panel title="Evidence">
              {attachments.data?.map((asset) => (
                <div className="work-list-row" key={asset.id}>
                  <div>
                    <strong>{asset.name}</strong>
                    <small>
                      {asset.kind} · {Math.ceil(asset.byte_size / 1024)} KB
                    </small>
                  </div>
                  <ActionButton
                    action={async () => {
                      const url = await evidenceUrl(
                        asset.id,
                        session.user.role === "organization"
                          ? "Review supporting task instructions"
                          : "",
                      );
                      const link = document.createElement("a");
                      link.href = url;
                      link.download = asset.name;
                      link.click();
                      setTimeout(() => URL.revokeObjectURL(url), 1000);
                    }}
                  >
                    {t("Download", "डाउनलोड")}
                  </ActionButton>
                </div>
              ))}
              {!worker && item.status !== "closed" && (
                <label className="form-field">
                  {t("Attach supporting instructions", "सहायक निर्देश जोड़ें")}
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp,video/mp4,video/webm,application/pdf"
                    onChange={async (event) => {
                      const file = event.target.files?.[0];
                      if (!file) return;
                      setAttachmentError(null);
                      try {
                        const body = new FormData();
                        body.set("file", file);
                        body.set(
                          "kind",
                          file.type.startsWith("image/")
                            ? "photo"
                            : file.type.startsWith("video/")
                              ? "video"
                              : "document",
                        );
                        body.set("department_id", item.department_id);
                        const uploaded = await api<Asset>("/files", {
                          method: "POST",
                          body,
                        });
                        await post(`/tasks/${id}/evidence`, {
                          asset_id: uploaded.id,
                        });
                        await attachments.refetch();
                      } catch (cause) {
                        setAttachmentError(cause);
                      }
                    }}
                  />
                </label>
              )}
              {!!attachmentError && <ErrorNotice error={attachmentError} />}
              {!attachments.data?.length && (
                <p className="work-note">
                  {t(
                    "No supporting files attached.",
                    "सहायक फ़ाइलें नहीं हैं।",
                  )}
                </p>
              )}
            </Panel>
            <Panel title="History">
              <ol className="work-timeline">
                {item.history?.map((event) => (
                  <li key={event.id}>
                    <span className="timeline-dot" />
                    <div>
                      <strong>{w(event.action)}</strong>
                      <p>
                        {str(event.detail.reason as string)}{" "}
                        {event.detail.from
                          ? `${w(String(event.detail.from))} → ${w(String(event.detail.to))}`
                          : ""}
                      </p>
                      <small>
                        {formatDate(
                          event.created_at,
                          session.organization.timezone,
                        )}
                      </small>
                    </div>
                  </li>
                ))}
              </ol>
            </Panel>
            {item.dependencies?.length ? (
              <Panel title="Dependencies">
                {item.dependencies.map((dependency) => (
                  <Link
                    className="text-link"
                    key={dependency}
                    to={`/workspace/tasks/${dependency}`}
                  >
                    {t("Open prerequisite task", "आवश्यक पहले का कार्य खोलें")}{" "}
                    →
                  </Link>
                ))}
              </Panel>
            ) : null}
            {modal && (
              <Modal
                title={
                  actionLabel[modal] ||
                  (modal === "comment"
                    ? "Add comment"
                    : modal === "edit"
                      ? t("Edit task", "कार्य बदलें")
                      : "Reassign")
                }
                onClose={() => setModal(null)}
              >
                {modal === "comment" ? (
                  <FieldsForm
                    fields={[
                      {
                        name: "text",
                        label: "Note",
                        type: "textarea",
                        required: true,
                      },
                      ...(!worker
                        ? [
                            {
                              name: "internal",
                              label: "Internal note",
                              type: "checkbox",
                            } as FieldSpec,
                          ]
                        : []),
                    ]}
                    onSubmit={(values) =>
                      post(`/tasks/${id}/comments`, {
                        ...values,
                        internal: values.internal || false,
                      })
                    }
                    onSuccess={() => setModal(null)}
                  />
                ) : modal === "reassign" ? (
                  <FieldsForm
                    fields={[
                      item.assignment_type === "individual"
                        ? {
                            name: "worker_id",
                            label: "Worker",
                            type: "select",
                            required: true,
                            options: options(
                              workers.data?.items.filter((p) => p.active),
                            ),
                          }
                        : {
                            name: "team_id",
                            label: "Team",
                            type: "select",
                            required: true,
                            options: options(
                              teams.data?.filter(
                                (team) =>
                                  team.active &&
                                  team.department_id === item.department_id,
                              ),
                            ),
                          },
                      {
                        name: "reason",
                        label: "Reason",
                        type: "textarea",
                        required: true,
                      },
                    ]}
                    onSubmit={(values) =>
                      post(`/tasks/${id}/reassign`, {
                        ...values,
                        version: item.version,
                      })
                    }
                    onSuccess={() => setModal(null)}
                  />
                ) : modal === "edit" ? (
                  <FieldsForm
                    fields={[
                      {
                        name: "title",
                        label: "Title",
                        required: true,
                        defaultValue: item.title,
                      },
                      {
                        name: "description",
                        label: "Description",
                        type: "textarea",
                        defaultValue: item.description,
                      },
                      {
                        name: "instructions",
                        label: "Instructions",
                        type: "textarea",
                        defaultValue: item.instructions,
                      },
                      {
                        name: "priority",
                        label: "Priority",
                        type: "select",
                        options: priorities.map((value) => ({
                          value,
                          label: value,
                        })),
                        defaultValue: item.priority || "",
                      },
                      {
                        name: "deadline",
                        label: "Deadline",
                        type: "datetime-local",
                        defaultValue: item.deadline
                          ? new Date(
                              Date.parse(item.deadline) -
                                new Date().getTimezoneOffset() * 60_000,
                            )
                              .toISOString()
                              .slice(0, 16)
                          : "",
                      },
                      {
                        name: "critical",
                        label: "Critical",
                        type: "checkbox",
                        defaultValue: item.critical,
                      },
                      {
                        name: "verification_required",
                        label: "Review required",
                        type: "checkbox",
                        defaultValue: item.verification_required,
                      },
                      { name: "reason", label: "Reason", required: true },
                    ]}
                    onSubmit={(values) =>
                      put(`/tasks/${id}`, {
                        ...values,
                        priority: nullable(values.priority),
                        deadline: iso(values.deadline),
                        version: item.version,
                      })
                    }
                    onSuccess={() => setModal(null)}
                  />
                ) : (
                  <FieldsForm
                    fields={[
                      {
                        name: "reason",
                        label: "Reason",
                        type: "textarea",
                        required: true,
                      },
                    ]}
                    onSubmit={(values) =>
                      post(`/tasks/${id}/actions`, {
                        ...values,
                        action: modal,
                        version: item.version,
                      })
                    }
                    onSuccess={() => setModal(null)}
                  />
                )}
              </Modal>
            )}
          </>
        )}
      </When>
    </>
  );
}
