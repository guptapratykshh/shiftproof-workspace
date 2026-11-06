import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { Copy, Plus, Upload } from "lucide-react";
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
} from "../../components/workspace/UI";
import { API_BASE, api, post, put, search } from "../../lib/api";
import { useSession } from "../../lib/session";
import { usePreferences } from "../../lib/preferences";
import type { Paged, Person, Task } from "../../lib/types";

function WorkerForm({
  person,
  onSaved,
}: {
  person?: Person;
  onSaved: (person: Person) => void;
}) {
  const { departments, teams, shifts } = useCatalog();
  const { t } = usePreferences();
  const active = person?.departments?.filter((m) => m.active) || [];
  return (
    <FieldsForm
      fields={[
        {
          name: "name",
          label: "Full name",
          required: true,
          defaultValue: person?.name,
        },
        {
          name: "employee_code",
          label: "Employee ID",
          defaultValue: person?.employee_code || "",
          hint: person
            ? t("Employee IDs remain stable.", "कर्मचारी आईडी स्थायी रहती है।")
            : t(
                "Leave blank to generate an ID.",
                "आईडी बनाने के लिए खाली छोड़ें।",
              ),
        },
        { name: "phone", label: "Contact number", defaultValue: person?.phone },
        {
          name: "primary_department_id",
          label: "Primary department",
          type: "select",
          required: true,
          options: options(departments.data?.filter((d) => d.active)),
          defaultValue: active.find((m) => m.primary)?.department_id,
        },
        {
          name: "additional",
          label: "Additional departments",
          type: "multi",
          options: options(departments.data?.filter((d) => d.active)),
          defaultValue: active
            .filter((m) => !m.primary)
            .map((m) => m.department_id),
        },
        {
          name: "team_ids",
          label: "Teams",
          type: "multi",
          options: teams.data
            ?.filter((team) => team.active)
            .map((team) => ({
              value: team.id,
              label: `${departments.data?.find((d) => d.id === team.department_id)?.name} / ${team.name}`,
            })),
          defaultValue: person?.teams
            ?.filter((m) => m.active)
            .map((m) => m.team_id),
        },
        {
          name: "skills",
          label: "Skills",
          defaultValue: person?.skills?.map((skill) => skill.name).join(", "),
          hint: t(
            "Separate qualifications with commas.",
            "योग्यताओं को कॉमा से अलग करें।",
          ),
        },
        {
          name: "shift_id",
          label: "Shift",
          type: "select",
          options: options(shifts.data?.filter((shift) => shift.active)),
        },
      ]}
      onSubmit={(values) => {
        const payload = {
          name: values.name,
          employee_code: nullable(values.employee_code),
          phone: values.phone,
          primary_department_id: values.primary_department_id,
          department_ids: [
            ...new Set([
              str(values.primary_department_id),
              ...list(values.additional),
            ]),
          ],
          team_ids: list(values.team_ids),
          skills: commaList(values.skills),
          shift_id: nullable(values.shift_id),
          profile: person?.profile || {},
        };
        return person
          ? put(`/workers/${person.id}`, payload)
          : post("/workers", payload);
      }}
      onSuccess={(result) => onSaved(result as Person)}
    >
      <p className="field-hint">
        {t(
          "Workers set their own six-digit PIN using a private activation link. No email address is needed.",
          "कर्मचारी निजी सक्रियण लिंक से अपना छह अंकों का पिन बनाते हैं। ईमेल आवश्यक नहीं है।",
        )}
      </p>
    </FieldsForm>
  );
}

export function ActivationInstructions({
  person,
}: {
  person: Pick<Person, "name" | "employee_code" | "activation_url">;
}) {
  const session = useSession((state) => state.session)!;
  const { t } = usePreferences();
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<unknown>(null);
  return (
    <div className="activation-instructions">
      <h3>{t("Private activation instructions", "निजी सक्रियण निर्देश")}</h3>
      <p>
        {person.name} · {person.employee_code}
      </p>
      <p>
        {t("Organization ID", "संगठन आईडी")}:{" "}
        <strong>{session.organization.code}</strong>
      </p>
      <p>
        {t(
          "Give this link only to the intended worker. They will choose their own PIN.",
          "यह लिंक केवल संबंधित कर्मचारी को दें। वे अपना पिन स्वयं चुनेंगे।",
        )}
      </p>
      <a className="private-link" href={person.activation_url}>
        {person.activation_url}
      </a>
      <button
        className="button button-outline"
        onClick={() => {
          void navigator.clipboard
            .writeText(
              `${session.organization.code}\n${person.employee_code}\n${person.activation_url}`,
            )
            .then(() => setCopied(true))
            .catch(setError);
        }}
      >
        <Copy size={16} />
        {copied
          ? t("Copied", "कॉपी किया")
          : t("Copy instructions", "निर्देश कॉपी करें")}
      </button>
      {!!error && <ErrorNotice error={error} />}
    </div>
  );
}

export function WorkforcePage() {
  const { departments, teams, shifts } = useCatalog();
  const { t } = usePreferences();
  const w = useWords();
  const [filter, setFilter] = useState({
    q: "",
    department_id: "",
    team_id: "",
    shift_id: "",
    active: "",
  });
  const [page, setPage] = useState(1);
  const [adding, setAdding] = useState(false);
  const [importing, setImporting] = useState(false);
  const [created, setCreated] = useState<Person | null>(null);
  const workers = useQuery({
    queryKey: ["workers", filter, page],
    queryFn: () =>
      api<Paged<Person>>(`/workers${search({ ...filter, page, limit: 25 })}`),
  });
  return (
    <>
      <PageTitle
        title="Workforce"
        description={t(
          "One account per worker, with clear departments, skills and responsibility.",
          "हर कर्मचारी का एक खाता, स्पष्ट विभाग, योग्यताएँ और जिम्मेदारी।",
        )}
      >
        <button
          className="button button-outline"
          onClick={() => setImporting(true)}
        >
          <Upload size={17} />
          {w("Import workers")}
        </button>
        <button
          className="button button-primary"
          onClick={() => setAdding(true)}
        >
          <Plus size={17} />
          {w("Add worker")}
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
        {(
          [
            {
              key: "department_id",
              label: "Department",
              items: departments.data,
            },
            { key: "team_id", label: "Team", items: teams.data },
            { key: "shift_id", label: "Shift", items: shifts.data },
          ] as const
        ).map((item) => (
          <label key={item.key}>
            {w(item.label)}
            <select
              value={filter[item.key]}
              onChange={(event) => {
                setFilter({ ...filter, [item.key]: event.target.value });
                setPage(1);
              }}
            >
              <option value="">{w("All")}</option>
              {item.items?.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.name}
                </option>
              ))}
            </select>
          </label>
        ))}
        <label>
          {w("Status")}
          <select
            value={filter.active}
            onChange={(event) => {
              setFilter({ ...filter, active: event.target.value });
              setPage(1);
            }}
          >
            <option value="">{w("All")}</option>
            <option value="true">{w("Active")}</option>
            <option value="false">{w("Inactive")}</option>
          </select>
        </label>
      </FilterBar>
      <Panel>
        <When loading={workers.isLoading} error={workers.error}>
          {!workers.data?.items.length ? (
            <Empty>
              {t(
                "Add a worker or import a reviewed CSV/Excel file.",
                "कर्मचारी जोड़ें या जाँची हुई CSV/Excel फ़ाइल आयात करें।",
              )}
            </Empty>
          ) : (
            <div className="work-card-grid">
              {workers.data.items.map((worker) => (
                <Link
                  className="person-card"
                  to={`/workspace/workforce/${worker.id}`}
                  key={worker.id}
                >
                  <span className="person-avatar">
                    {worker.name.slice(0, 2).toUpperCase()}
                  </span>
                  <h3>{worker.name}</h3>
                  <p>{worker.employee_code}</p>
                  <Status
                    value={
                      worker.active
                        ? "Active"
                        : worker.verified
                          ? "Inactive"
                          : "Pending"
                    }
                  />
                  <p>
                    {worker.departments
                      ?.filter((m) => m.active)
                      .map(
                        (m) =>
                          departments.data?.find(
                            (d) => d.id === m.department_id,
                          )?.name,
                      )
                      .join(" · ")}
                  </p>
                  <span className="text-link">{w("View details")} →</span>
                </Link>
              ))}
            </div>
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
          {page} / {Math.max(1, Math.ceil((workers.data?.total || 0) / 25))}
        </span>
        <button
          className="button button-outline"
          disabled={page * 25 >= (workers.data?.total || 0)}
          onClick={() => setPage(page + 1)}
        >
          {w("Next page")}
        </button>
      </div>
      {adding && (
        <Modal title="Add worker" onClose={() => setAdding(false)}>
          <WorkerForm
            onSaved={(person) => {
              setAdding(false);
              setCreated(person);
            }}
          />
        </Modal>
      )}
      {created && (
        <Modal title="Worker" onClose={() => setCreated(null)}>
          <ActivationInstructions person={created} />
        </Modal>
      )}
      {importing && (
        <Modal title="Import workers" onClose={() => setImporting(false)}>
          <WorkerImport />
        </Modal>
      )}
    </>
  );
}

export function WorkerDetailPage() {
  const { id } = useParams();
  const session = useSession((state) => state.session)!;
  const { departments, teams, shifts } = useCatalog();
  const { t } = usePreferences();
  const w = useWords();
  const person = useQuery({
    queryKey: ["worker", id],
    queryFn: () => api<Person>(`/workers/${id}`),
  });
  const tasks = useQuery({
    queryKey: ["tasks", "worker", id],
    queryFn: () => api<Paged<Task>>(`/tasks?worker_id=${id}&limit=200`),
  });
  const [qualification, setQualification] = useState<
    NonNullable<Person["skills"]>[number] | null
  >(null);
  const [modal, setModal] = useState<
    "edit" | "pin" | "absence" | "state" | null
  >(null);
  const [availabilityEdit, setAvailabilityEdit] = useState<
    NonNullable<Person["availability"]>[number] | null
  >(null);
  const [activation, setActivation] = useState<string | null>(null);
  return (
    <>
      <PageTitle title={person.data?.name || "Worker"} />
      <When loading={person.isLoading} error={person.error}>
        {person.data && (
          <>
            <Panel>
              <div className="work-actions section-actions">
                <button
                  className="button button-outline"
                  onClick={() => setModal("edit")}
                >
                  {t("Edit profile", "प्रोफ़ाइल बदलें")}
                </button>
                <button
                  className="button button-outline"
                  onClick={() => {
                    setAvailabilityEdit(null);
                    setModal("absence");
                  }}
                >
                  {w("Mark availability")}
                </button>
                <button
                  className="button button-outline"
                  onClick={() => setModal("pin")}
                >
                  {w("Reset PIN")}
                </button>
                {session.user.role === "organization" && (
                  <button
                    className="button button-outline"
                    onClick={() => setModal("state")}
                  >
                    {w(person.data.active ? "Deactivate" : "Reactivate")}
                  </button>
                )}
              </div>
              <dl className="work-definition">
                <div>
                  <dt>{w("Employee ID")}</dt>
                  <dd>{person.data.employee_code}</dd>
                </div>
                <div>
                  <dt>{w("Status")}</dt>
                  <dd>
                    <Status
                      value={person.data.active ? "Active" : "Inactive"}
                    />
                  </dd>
                </div>
                <div>
                  <dt>{w("Departments")}</dt>
                  <dd>
                    {person.data.departments
                      ?.filter((m) => m.active)
                      .map(
                        (m) =>
                          `${departments.data?.find((d) => d.id === m.department_id)?.name}${m.primary ? ` (${w("Primary")})` : ""}`,
                      )
                      .join(", ")}
                  </dd>
                </div>
                <div>
                  <dt>{w("Teams")}</dt>
                  <dd>
                    {person.data.teams
                      ?.filter((m) => m.active)
                      .map(
                        (m) =>
                          teams.data?.find((team) => team.id === m.team_id)
                            ?.name,
                      )
                      .join(", ") || "—"}
                  </dd>
                </div>
                <div>
                  <dt>{w("Shifts")}</dt>
                  <dd>
                    {person.data.shifts
                      ?.filter((m) => m.active)
                      .map(
                        (m) =>
                          shifts.data?.find((shift) => shift.id === m.shift_id)
                            ?.name,
                      )
                      .join(", ") || "—"}
                  </dd>
                </div>
                <div>
                  <dt>{w("Skills")}</dt>
                  <dd>
                    {person.data.skills
                      ?.map((skill) => skill.name)
                      .join(", ") || "—"}
                  </dd>
                </div>
              </dl>
            </Panel>
            <Panel title={t("Qualifications", "योग्यताएँ")}>
              {!person.data.skills?.length ? (
                <Empty>
                  {t(
                    "Add skills in the worker profile first.",
                    "पहले कर्मचारी प्रोफ़ाइल में कौशल जोड़ें।",
                  )}
                </Empty>
              ) : (
                person.data.skills.map((skill) => (
                  <div className="work-list-row" key={skill.id}>
                    <div>
                      <strong>{skill.name}</strong>
                      <p>
                        {skill.qualification ||
                          t(
                            "No certificate reference",
                            "प्रमाणपत्र संदर्भ नहीं है",
                          )}
                      </p>
                      <small>
                        {skill.expires_on
                          ? `${t("Expires", "मान्य तिथि")}: ${skill.expires_on}`
                          : t(
                              "No expiry recorded",
                              "समाप्ति तिथि दर्ज नहीं है",
                            )}
                      </small>
                    </div>
                    <button
                      className="button button-outline"
                      onClick={() => setQualification(skill)}
                    >
                      {w("Edit")}
                    </button>
                  </div>
                ))
              )}
            </Panel>
            {qualification && (
              <Modal
                title={t("Qualification details", "योग्यता विवरण")}
                onClose={() => setQualification(null)}
              >
                <FieldsForm
                  fields={[
                    {
                      name: "qualification",
                      label: t(
                        "Certificate / qualification reference",
                        "प्रमाणपत्र / योग्यता संदर्भ",
                      ),
                      defaultValue: qualification.qualification,
                    },
                    {
                      name: "expires_on",
                      label: t("Valid through", "तक मान्य"),
                      type: "date",
                      defaultValue: qualification.expires_on || "",
                    },
                  ]}
                  onSubmit={(values) =>
                    put(`/workers/${id}/qualifications/${qualification.id}`, {
                      ...values,
                      expires_on: nullable(values.expires_on),
                    })
                  }
                  onSuccess={() => setQualification(null)}
                />
              </Modal>
            )}
            <Panel title="Tasks">
              <When loading={tasks.isLoading} error={tasks.error}>
                {!tasks.data?.items.length ? (
                  <Empty />
                ) : (
                  tasks.data.items.map((task) => (
                    <Link
                      className="work-list-row"
                      to={`/workspace/tasks/${task.id}`}
                      key={task.id}
                    >
                      <div>
                        <strong>{task.title}</strong>
                        <p>
                          {task.critical &&
                            t(
                              "Critical · approval required",
                              "गंभीर · मंज़ूरी आवश्यक",
                            )}
                        </p>
                      </div>
                      <Status value={task.status} />
                    </Link>
                  ))
                )}
              </When>
            </Panel>
            <Panel title="Availability history">
              {!person.data.availability?.length ? (
                <Empty />
              ) : (
                person.data.availability.map((item, index) => (
                  <div className="work-list-row" key={index}>
                    <div>
                      <Status value={item.status} />
                      <p>
                        {formatDate(item.starts_at)} —{" "}
                        {formatDate(item.ends_at)}
                      </p>
                    </div>
                    <p>{item.reason}</p>
                    <button
                      className="button button-outline"
                      onClick={() => {
                        setAvailabilityEdit(item);
                        setModal("absence");
                      }}
                    >
                      {t("Correct availability", "उपलब्धता सुधारें")}
                    </button>
                  </div>
                ))
              )}
            </Panel>
            {modal && (
              <Modal
                title={
                  modal === "edit"
                    ? "Worker"
                    : modal === "pin"
                      ? "Reset PIN"
                      : modal === "absence"
                        ? "Mark availability"
                        : person.data.active
                          ? "Deactivate"
                          : "Reactivate"
                }
                onClose={() => setModal(null)}
              >
                {modal === "edit" ? (
                  <WorkerForm
                    person={person.data}
                    onSaved={() => setModal(null)}
                  />
                ) : modal === "pin" ? (
                  <FieldsForm
                    fields={[
                      {
                        name: "identity_verified",
                        label: "Identity verified",
                        type: "checkbox",
                        required: true,
                      },
                      {
                        name: "verification_note",
                        label: "Verification note",
                        type: "textarea",
                        required: true,
                      },
                    ]}
                    onSubmit={(values) =>
                      post(`/workers/${id}/pin-reset`, values)
                    }
                    onSuccess={(result) => {
                      setActivation(
                        (result as { activation_url: string }).activation_url,
                      );
                      setModal(null);
                    }}
                  />
                ) : modal === "state" ? (
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
                      put(`/users/${id}/state`, {
                        ...values,
                        active: !person.data!.active,
                      })
                    }
                    onSuccess={() => setModal(null)}
                  />
                ) : (
                  <FieldsForm
                    fields={[
                      {
                        name: "starts_at",
                        defaultValue: availabilityEdit
                          ? localDateTime(availabilityEdit.starts_at)
                          : "",
                        label: "Start time",
                        type: "datetime-local",
                        required: true,
                      },
                      {
                        name: "ends_at",
                        defaultValue: availabilityEdit
                          ? localDateTime(availabilityEdit.ends_at)
                          : "",
                        label: "End time",
                        type: "datetime-local",
                        required: true,
                      },
                      {
                        name: "status",
                        defaultValue: availabilityEdit?.status,
                        label: "Status",
                        type: "select",
                        required: true,
                        options: [
                          "absent",
                          "unavailable",
                          "leave",
                          "available",
                        ].map((value) => ({ value, label: value })),
                      },
                      {
                        name: "reason",
                        defaultValue: availabilityEdit?.reason,
                        label: "Reason",
                        type: "textarea",
                        required: true,
                      },
                    ]}
                    onSubmit={(values) =>
                      (availabilityEdit ? put : post)(
                        `/workers/${id}/availability${availabilityEdit ? `/${availabilityEdit.id}` : ""}`,
                        {
                          ...values,
                          starts_at: iso(values.starts_at),
                          ends_at: iso(values.ends_at),
                        },
                      )
                    }
                    onSuccess={() => setModal(null)}
                  >
                    <p className="work-warning">
                      {t(
                        "Existing work stays open. Review pending tasks and reassign critical work immediately.",
                        "मौजूदा कार्य खुले रहेंगे। लंबित कार्य देखें और गंभीर कार्य तुरंत दूसरे कर्मचारी को सौंपें।",
                      )}
                    </p>
                  </FieldsForm>
                )}
              </Modal>
            )}
            {activation && (
              <Modal title="Reset PIN" onClose={() => setActivation(null)}>
                <ActivationInstructions
                  person={{ ...person.data, activation_url: activation }}
                />
              </Modal>
            )}
          </>
        )}
      </When>
    </>
  );
}

type Preview = {
  id: string;
  valid: number;
  invalid: number;
  rows: {
    row: number;
    valid: boolean;
    errors: string[];
    input: Record<string, string>;
  }[];
};
export function WorkerImport() {
  const { t } = usePreferences();
  const w = useWords();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [result, setResult] = useState<{
    created: number;
    skipped_invalid: number;
    workers: Person[];
  } | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  return (
    <div className="work-stack">
      <p>
        {t(
          "Use department, team and shift names exactly as configured. Separate multiple departments, teams and skills with semicolons. No accounts are created until you confirm the preview.",
          "विभाग, टीम और शिफ्ट के नाम सेटअप के अनुसार भरें। कई नाम सेमीकोलन से अलग करें। जाँच की पुष्टि तक खाते नहीं बनेंगे।",
        )}
      </p>
      <a
        className="button button-outline"
        href={`${API_BASE}/worker-imports/template`}
        download
      >
        {w("Download template")}
      </a>
      <label className="form-field">
        {w("Choose file")}
        <input
          type="file"
          accept=".csv,.xlsx"
          onChange={(event) => {
            setFile(event.target.files?.[0] || null);
            setPreview(null);
            setResult(null);
          }}
        />
      </label>
      <button
        className="button button-primary"
        disabled={!file || busy}
        onClick={async () => {
          if (!file) return;
          setError(null);
          setBusy(true);
          try {
            const body = new FormData();
            body.set("file", file);
            setPreview(
              await api<Preview>("/worker-imports/preview", {
                method: "POST",
                body,
              }),
            );
          } catch (cause) {
            setError(cause);
          } finally {
            setBusy(false);
          }
        }}
      >
        {w(busy ? "Loading…" : "Upload preview")}
      </button>
      {!!error && <ErrorNotice error={error} />}
      {preview && !result && (
        <>
          <p>
            <strong>{preview.valid}</strong> {t("valid rows", "सही पंक्तियाँ")}{" "}
            · <strong>{preview.invalid}</strong>{" "}
            {t("invalid rows", "गलत पंक्तियाँ")}
          </p>
          <div className="import-preview">
            {preview.rows.map((row) => (
              <div className="work-list-row" key={row.row}>
                <div>
                  <strong>
                    {row.row}. {row.input.full_name}
                  </strong>
                  <p>
                    {row.input.employee_id} · {row.input.primary_department}
                  </p>
                  {row.errors.map((error) => (
                    <p className="field-error" key={error}>
                      {error}
                    </p>
                  ))}
                </div>
                <Status value={row.valid ? "Active" : "Invalid"} />
              </div>
            ))}
          </div>
          <ActionButton
            className="button button-primary"
            action={async () =>
              setResult(
                await post(`/worker-imports/${preview.id}/confirm`, {
                  confirm_valid_rows_only: true,
                }),
              )
            }
          >
            {w("Confirm valid rows")} ({preview.valid})
          </ActionButton>
          {preview.invalid > 0 && (
            <p className="work-warning">
              {t(
                "This explicitly imports only valid rows. Invalid rows remain excluded; correct and upload them separately.",
                "इस पुष्टि से केवल सही पंक्तियाँ आयात होंगी। गलत पंक्तियाँ सुधारकर अलग अपलोड करें।",
              )}
            </p>
          )}
        </>
      )}
      {result && (
        <>
          <p className="work-success">
            {result.created} {t("workers created", "कर्मचारी बनाए गए")} ·{" "}
            {result.skipped_invalid}{" "}
            {t("invalid rows excluded", "गलत पंक्तियाँ छोड़ी गईं")}
          </p>
          {result.workers.map((person) => (
            <ActivationInstructions key={person.id} person={person} />
          ))}
        </>
      )}
    </div>
  );
}

function localDateTime(value: string) {
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
}
