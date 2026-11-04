import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { CheckCircle2, Plus } from "lucide-react";
import { useCatalog } from "../../components/workspace/Workspace";
import {
  ActionButton,
  Empty,
  FieldsForm,
  Modal,
  PageTitle,
  Panel,
  Status,
  When,
  formatDate,
  list,
  nullable,
  options,
  str,
  useWords,
  type FieldSpec,
} from "../../components/workspace/UI";
import { api, post, put, remove } from "../../lib/api";
import { useSession } from "../../lib/session";
import { usePreferences } from "../../lib/preferences";
import { industries } from "../../lib/industries";
import type {
  Department,
  Person,
  Shift,
  ShiftAssignment,
  Team,
} from "../../lib/types";

export function OrganizationProfile({ onSaved }: { onSaved?: () => void }) {
  const session = useSession((state) => state.session)!;
  const { t } = usePreferences();
  const organization = session.organization;
  return (
    <FieldsForm
      key={organization.id}
      fields={[
        {
          name: "name",
          label: "Organization name",
          required: true,
          defaultValue: organization.name,
        },
        {
          name: "industry",
          label: "Organization type",
          type: "select",
          required: true,
          defaultValue: organization.industry,
          options: industries.map((item) => ({
            value: item.id,
            label: t(item.name, item.hi),
          })),
        },
        {
          name: "contact_email",
          label: "Official email",
          type: "email",
          required: true,
          defaultValue: str(organization.settings.contact_email as string),
        },
        {
          name: "timezone",
          label: "Timezone",
          required: true,
          defaultValue: organization.timezone,
          hint: t(
            "Use an IANA timezone, for example Asia/Kolkata.",
            "IANA समय क्षेत्र भरें, जैसे Asia/Kolkata।",
          ),
        },
        {
          name: "contact",
          label: "Contact number",
          defaultValue: organization.contact,
        },
        {
          name: "address",
          label: "Address",
          defaultValue: str(organization.settings.address as string),
        },
      ]}
      onSubmit={(values) =>
        put("/organization", {
          ...values,
          logo_asset_id: organization.settings.logo_asset_id || null,
        })
      }
      onSuccess={onSaved}
    />
  );
}

export function DepartmentsPage({ embedded = false }: { embedded?: boolean }) {
  const { departments, teams } = useCatalog();
  const w = useWords();
  const { t } = usePreferences();
  const [editor, setEditor] = useState<{
    kind: "department" | "team";
    item?: Department | Team;
  } | null>(null);
  const fields: FieldSpec[] = [
    {
      name: "name",
      label: "Name",
      required: true,
      defaultValue: editor?.item?.name,
    },
    {
      name: "description",
      label: "Description",
      type: "textarea",
      defaultValue: editor?.item?.description,
    },
  ];
  if (editor?.kind === "team")
    fields.unshift({
      name: "department_id",
      label: "Department",
      type: "select",
      required: true,
      options: options(departments.data?.filter((d) => d.active)),
      defaultValue: (editor.item as Team)?.department_id,
    });
  return (
    <>
      {!embedded && (
        <PageTitle
          title="Departments"
          description={t(
            "Keep the structure clear. Historical records remain when a department or team is deactivated.",
            "विभाग और टीम का ढाँचा स्पष्ट रखें। निष्क्रिय करने पर पुराने रिकॉर्ड सुरक्षित रहते हैं।",
          )}
        />
      )}
      <div className="work-two-column">
        <Panel
          title="Departments"
          action={
            <button
              className="button button-outline"
              onClick={() => setEditor({ kind: "department" })}
            >
              <Plus size={16} />
              {w("Create")}
            </button>
          }
        >
          <When loading={departments.isLoading} error={departments.error}>
            {!departments.data?.length ? (
              <Empty />
            ) : (
              departments.data.map((item) => (
                <div className="work-list-row" key={item.id}>
                  <div>
                    <Link
                      className="text-link"
                      to={`/workspace/departments/${item.id}`}
                    >
                      <strong>{item.name}</strong>
                    </Link>
                    <p>{item.description}</p>
                    <Status value={item.active ? "Active" : "Inactive"} />
                  </div>
                  <div className="work-actions">
                    <button
                      className="text-button"
                      onClick={() => setEditor({ kind: "department", item })}
                    >
                      {t("Edit", "संपादित करें")}
                    </button>
                    <ActionButton
                      action={() =>
                        put(`/departments/${item.id}`, {
                          name: item.name,
                          description: item.description,
                          active: !item.active,
                        })
                      }
                    >
                      {w(item.active ? "Deactivate" : "Reactivate")}
                    </ActionButton>
                  </div>
                </div>
              ))
            )}
          </When>
        </Panel>
        <Panel
          title="Teams"
          action={
            <button
              className="button button-outline"
              onClick={() => setEditor({ kind: "team" })}
            >
              <Plus size={16} />
              {w("Create")}
            </button>
          }
        >
          <When loading={teams.isLoading} error={teams.error}>
            {!teams.data?.length ? (
              <Empty />
            ) : (
              teams.data.map((item) => (
                <div className="work-list-row" key={item.id}>
                  <div>
                    <Link
                      className="text-link"
                      to={`/workspace/teams/${item.id}`}
                    >
                      <strong>{item.name}</strong>
                    </Link>
                    <p>
                      {
                        departments.data?.find(
                          (d) => d.id === item.department_id,
                        )?.name
                      }
                    </p>
                    <Status value={item.active ? "Active" : "Inactive"} />
                  </div>
                  <div className="work-actions">
                    <button
                      className="text-button"
                      onClick={() => setEditor({ kind: "team", item })}
                    >
                      {t("Edit", "संपादित करें")}
                    </button>
                    <ActionButton
                      action={() =>
                        put(`/teams/${item.id}`, {
                          name: item.name,
                          description: item.description,
                          department_id: item.department_id,
                          active: !item.active,
                        })
                      }
                    >
                      {w(item.active ? "Deactivate" : "Reactivate")}
                    </ActionButton>
                  </div>
                </div>
              ))
            )}
          </When>
        </Panel>
      </div>
      {editor && (
        <Modal
          title={editor.kind === "team" ? "Team" : "Department"}
          onClose={() => setEditor(null)}
        >
          <FieldsForm
            fields={fields}
            onSubmit={(values) =>
              editor.item
                ? put(
                    `/${editor.kind === "team" ? "teams" : "departments"}/${editor.item.id}`,
                    { ...values, active: editor.item.active },
                  )
                : post(
                    `/${editor.kind === "team" ? "teams" : "departments"}`,
                    values,
                  )
            }
            onSuccess={() => setEditor(null)}
          />
        </Modal>
      )}
    </>
  );
}

const dayOptions = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
].map((label, index) => ({ label, value: String(index) }));
function WeeklySchedule({
  assignments,
  people,
  shifts,
}: {
  assignments: ShiftAssignment[];
  people: Person[];
  shifts: Shift[];
}) {
  const { t, language } = usePreferences();
  const zone = useSession((state) => state.session)!.organization.timezone;
  const [week, setWeek] = useState(0);
  const localDay = new Intl.DateTimeFormat("en-CA", {
    timeZone: zone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
  const monday = new Date(`${localDay}T12:00:00Z`);
  monday.setUTCDate(
    monday.getUTCDate() - ((monday.getUTCDay() + 6) % 7) + week * 7,
  );
  const days = Array.from({ length: 7 }, (_, i) => {
    const day = new Date(monday);
    day.setUTCDate(day.getUTCDate() + i);
    return day;
  });
  return (
    <Panel
      title={t("Weekly coverage", "साप्ताहिक जिम्मेदारी")}
      action={
        <div className="work-actions">
          <button
            className="button button-outline"
            onClick={() => setWeek(week - 1)}
            aria-label={t("Previous week", "पिछला सप्ताह")}
          >
            ←
          </button>
          <button className="button button-outline" onClick={() => setWeek(0)}>
            {t("This week", "यह सप्ताह")}
          </button>
          <button
            className="button button-outline"
            onClick={() => setWeek(week + 1)}
            aria-label={t("Next week", "अगला सप्ताह")}
          >
            →
          </button>
        </div>
      }
    >
      <div className="weekly-calendar">
        {days.map((day, index) => {
          const date = day.toISOString().slice(0, 10);
          return (
            <article key={date} className="week-day">
              <h3>
                {new Intl.DateTimeFormat(language, {
                  timeZone: "UTC",
                  weekday: "short",
                  day: "numeric",
                  month: "short",
                }).format(day)}
              </h3>
              {shifts
                .filter((s) => s.active && s.days.includes(index))
                .map((shift) => {
                  const members = assignments
                    .filter(
                      (a) =>
                        a.active &&
                        a.shift_id === shift.id &&
                        a.starts_on <= date &&
                        (!a.ends_on || a.ends_on >= date),
                    )
                    .map((a) => people.find((p) => p.id === a.user_id))
                    .filter((p): p is Person => !!p && p.active);
                  return (
                    <div className="week-shift" key={shift.id}>
                      <strong>{shift.name}</strong>
                      <small>
                        {shift.starts_at}–{shift.ends_at}
                        {shift.ends_at < shift.starts_at ? " +1" : ""}
                      </small>
                      <p>
                        {members.length
                          ? [...new Map(members.map((p) => [p.id, p])).values()]
                              .map((p) => p.name)
                              .join(", ")
                          : t("No assigned coverage", "कोई जिम्मेदारी तय नहीं")}
                      </p>
                    </div>
                  );
                })}
            </article>
          );
        })}
      </div>
    </Panel>
  );
}

export function ShiftsPage({ embedded = false }: { embedded?: boolean }) {
  const session = useSession((state) => state.session)!;
  const admin = session.user.role === "organization";
  const { departments, shifts, workers, supervisors } = useCatalog();
  const { t } = usePreferences();
  const w = useWords();
  const [editor, setEditor] = useState<Shift | "new" | null>(null);
  const [assigning, setAssigning] = useState(false);
  const [warnings, setWarnings] = useState<string[]>([]);
  const assignments = useQuery({
    queryKey: ["shift-assignments"],
    queryFn: () => api<ShiftAssignment[]>("/shift-assignments"),
  });
  const item = editor && editor !== "new" ? editor : null;
  const people = [
    ...(workers.data?.items || []),
    ...(supervisors.data || []).filter((p) => p.role === "supervisor"),
  ];
  return (
    <>
      {!embedded && (
        <PageTitle
          title="Shifts"
          description={t(
            "Times use your organization’s timezone. Overnight shifts continue into the following day.",
            "समय संगठन के समय क्षेत्र के अनुसार है। रात की शिफ्ट अगले दिन तक चलती है।",
          )}
        >
          <button
            className="button button-primary"
            onClick={() => setAssigning(true)}
          >
            {w("Assign shift")}
          </button>
        </PageTitle>
      )}
      <Panel
        title="Shifts"
        action={
          admin && (
            <button
              className="button button-outline"
              onClick={() => setEditor("new")}
            >
              <Plus size={16} />
              {w("Create")}
            </button>
          )
        }
      >
        <When loading={shifts.isLoading} error={shifts.error}>
          {!shifts.data?.length ? (
            <Empty />
          ) : (
            <div className="shift-grid">
              {shifts.data.map((shift) => (
                <article key={shift.id} className="shift-card">
                  <div className="panel-heading">
                    <h3>{shift.name}</h3>
                    <Status value={shift.active ? "Active" : "Inactive"} />
                  </div>
                  <p className="shift-time">
                    {shift.starts_at} — {shift.ends_at}
                    <small>
                      {shift.ends_at < shift.starts_at &&
                        t("next day", "अगला दिन")}
                    </small>
                  </p>
                  <div
                    className="shift-track"
                    aria-label={`${shift.starts_at}–${shift.ends_at}`}
                  >
                    {(() => {
                      const minutes = (value: string) =>
                        Number(value.slice(0, 2)) * 60 + Number(value.slice(3));
                      const start = minutes(shift.starts_at);
                      const end = minutes(shift.ends_at);
                      const blocks =
                        end > start
                          ? [[start, end]]
                          : [
                              [start, 1440],
                              [0, end],
                            ];
                      return blocks.map(([from, to], index) => (
                        <span
                          key={index}
                          style={{
                            left: `${from / 14.4}%`,
                            width: `${(to - from) / 14.4}%`,
                          }}
                        />
                      ));
                    })()}
                  </div>
                  <div className="shift-track-labels">
                    <span>00:00</span>
                    <span>12:00</span>
                    <span>24:00</span>
                  </div>
                  <div className="shift-days">
                    {dayOptions.map((day) => (
                      <span
                        key={day.value}
                        className={
                          shift.days.includes(Number(day.value))
                            ? "day-active"
                            : ""
                        }
                      >
                        {t(
                          day.label.slice(0, 3),
                          ["सोम", "मंगल", "बुध", "गुरु", "शुक्र", "शनि", "रवि"][
                            Number(day.value)
                          ],
                        )}
                      </span>
                    ))}
                  </div>
                  {admin && (
                    <div className="work-actions">
                      <button
                        className="text-button"
                        onClick={() => setEditor(shift)}
                      >
                        {t("Edit", "संपादित करें")}
                      </button>
                      <ActionButton
                        action={() =>
                          put(`/shifts/${shift.id}`, {
                            name: shift.name,
                            starts_at: shift.starts_at,
                            ends_at: shift.ends_at,
                            days: shift.days,
                            rotation: shift.rotation,
                            grace_minutes: shift.grace_minutes,
                            active: !shift.active,
                          })
                        }
                      >
                        {w(shift.active ? "Deactivate" : "Reactivate")}
                      </ActionButton>
                    </div>
                  )}
                </article>
              ))}
            </div>
          )}
        </When>
        {warnings.map((warning) => (
          <p className="work-warning" key={warning}>
            {warning}
          </p>
        ))}
      </Panel>
      {!embedded && (
        <Panel
          title={t(
            "Department and shift coverage",
            "विभाग और शिफ्ट की जिम्मेदारी",
          )}
        >
          <div className="coverage-grid">
            {departments.data
              ?.filter((d) => d.active)
              .map((department) =>
                shifts.data
                  ?.filter((shift) => shift.active)
                  .map((shift) => {
                    const current =
                      assignments.data?.filter(
                        (a) =>
                          a.active &&
                          a.department_id === department.id &&
                          a.shift_id === shift.id &&
                          a.starts_on <=
                            new Date().toISOString().slice(0, 10) &&
                          (!a.ends_on ||
                            a.ends_on >= new Date().toISOString().slice(0, 10)),
                      ) || [];
                    const assigned = new Set(current.map((a) => a.user_id));
                    const primary = supervisors.data?.some(
                      (person) =>
                        assigned.has(person.id) &&
                        person.active &&
                        person.departments?.some(
                          (m) =>
                            m.department_id === department.id &&
                            m.active &&
                            m.primary,
                        ),
                    );
                    const backup = supervisors.data?.some(
                      (person) =>
                        assigned.has(person.id) &&
                        person.active &&
                        person.departments?.some(
                          (m) =>
                            m.department_id === department.id &&
                            m.active &&
                            m.backup,
                        ),
                    );
                    return (
                      <article
                        className="coverage-cell"
                        key={`${department.id}-${shift.id}`}
                      >
                        <h3>{department.name}</h3>
                        <p>{shift.name}</p>
                        <span>
                          {
                            current.filter((a) =>
                              workers.data?.items.some(
                                (p) => p.id === a.user_id,
                              ),
                            ).length
                          }{" "}
                          {t("workers scheduled", "कर्मचारी निर्धारित")}
                        </span>
                        <p
                          className={!primary ? "work-warning" : "work-success"}
                        >
                          {primary
                            ? t(
                                "Primary assigned",
                                "मुख्य पर्यवेक्षक निर्धारित",
                              )
                            : t(
                                "Primary shift coverage missing",
                                "मुख्य शिफ्ट पर्यवेक्षक नहीं है",
                              )}
                        </p>
                        <p
                          className={!backup ? "work-warning" : "work-success"}
                        >
                          {backup
                            ? t("Backup assigned", "बैकअप निर्धारित")
                            : t(
                                "Backup shift coverage missing",
                                "बैकअप शिफ्ट पर्यवेक्षक नहीं है",
                              )}
                        </p>
                      </article>
                    );
                  }),
              )}
          </div>
        </Panel>
      )}
      {!embedded && (
        <Panel title="Shift assignments">
          <When loading={assignments.isLoading} error={assignments.error}>
            {!assignments.data?.length ? (
              <Empty />
            ) : (
              assignments.data.map((assignment) => (
                <div className="work-list-row" key={assignment.id}>
                  <div>
                    <strong>
                      {people.find((p) => p.id === assignment.user_id)?.name ||
                        t("Assigned team member", "टीम सदस्य")}
                    </strong>
                    <p>
                      {
                        shifts.data?.find((s) => s.id === assignment.shift_id)
                          ?.name
                      }{" "}
                      ·{" "}
                      {
                        departments.data?.find(
                          (d) => d.id === assignment.department_id,
                        )?.name
                      }
                    </p>
                    <small>
                      {assignment.starts_on} —{" "}
                      {assignment.ends_on || t("Ongoing", "जारी")}
                    </small>
                  </div>
                  {assignment.active && (
                    <ActionButton
                      action={() =>
                        remove(`/shift-assignments/${assignment.id}`)
                      }
                    >
                      {t("End assignment", "जिम्मेदारी समाप्त करें")}
                    </ActionButton>
                  )}
                </div>
              ))
            )}
          </When>
        </Panel>
      )}
      {!embedded && (
        <WeeklySchedule
          assignments={assignments.data || []}
          people={people}
          shifts={shifts.data || []}
        />
      )}
      {editor && (
        <Modal title="Shift" onClose={() => setEditor(null)}>
          <FieldsForm
            fields={[
              {
                name: "name",
                label: "Name",
                required: true,
                defaultValue: item?.name,
              },
              {
                name: "starts_at",
                label: "Start time",
                type: "time",
                required: true,
                defaultValue: item?.starts_at,
              },
              {
                name: "ends_at",
                label: "End time",
                type: "time",
                required: true,
                defaultValue: item?.ends_at,
              },
              {
                name: "days",
                label: "Working days",
                type: "multi",
                required: true,
                options: dayOptions,
                defaultValue: item?.days.map(String) || [
                  "0",
                  "1",
                  "2",
                  "3",
                  "4",
                  "5",
                ],
              },
              {
                name: "grace_minutes",
                label: "Grace minutes",
                type: "number",
                min: 0,
                max: 120,
                defaultValue: item?.grace_minutes ?? 15,
              },
            ]}
            onSubmit={(values) => {
              const payload = {
                ...values,
                days: list(values.days).map(Number),
                grace_minutes: Number(values.grace_minutes),
                rotation: item?.rotation || {},
                active: item?.active ?? true,
              };
              return item
                ? put(`/shifts/${item.id}`, payload)
                : post("/shifts", payload);
            }}
            onSuccess={(result) => {
              setWarnings((result as Shift).warnings || []);
              setEditor(null);
            }}
          />
        </Modal>
      )}
      {assigning && (
        <Modal title="Assign shift" onClose={() => setAssigning(false)}>
          <FieldsForm
            fields={[
              {
                name: "user_id",
                label: "Member",
                type: "select",
                required: true,
                options: options(people.filter((p) => p.active)),
              },
              {
                name: "department_id",
                label: "Department",
                type: "select",
                required: true,
                options: options(departments.data?.filter((d) => d.active)),
              },
              {
                name: "shift_id",
                label: "Shift",
                type: "select",
                required: true,
                options: options(shifts.data?.filter((s) => s.active)),
              },
              {
                name: "starts_on",
                label: "Start date",
                type: "date",
                required: true,
                defaultValue: new Date().toISOString().slice(0, 10),
              },
              { name: "ends_on", label: "End date", type: "date" },
            ]}
            onSubmit={(values) =>
              post("/shift-assignments", {
                ...values,
                ends_on: nullable(values.ends_on),
              })
            }
            onSuccess={() => setAssigning(false)}
          />
        </Modal>
      )}
    </>
  );
}

function PermissionForm({
  person,
  onSaved,
}: {
  person?: Person;
  onSaved: () => void;
}) {
  const { departments } = useCatalog();
  const [memberships, setMemberships] = useState(person?.departments || []);
  const { t } = usePreferences();
  const w = useWords();
  const permissions = [
    "view",
    "manage",
    "review",
    "publish",
    "workforce",
    "evidence",
  ];
  const update = (
    departmentId: string,
    key: "primary" | "backup" | "permissions",
    value: boolean | string[],
  ) =>
    setMemberships((current) => {
      const existing = current.find((m) => m.department_id === departmentId);
      const base = existing || {
        department_id: departmentId,
        primary: false,
        backup: false,
        permissions: ["view"],
        active: true,
      };
      return [
        ...current.filter((m) => m.department_id !== departmentId),
        { ...base, [key]: value } as (typeof memberships)[number],
      ];
    });
  return (
    <FieldsForm
      fields={
        person
          ? []
          : [
              { name: "name", label: "Full name", required: true },
              {
                name: "email",
                label: "Official email",
                type: "email",
                required: true,
              },
              { name: "phone", label: "Contact number" },
            ]
      }
      onSubmit={(values) => {
        const payload = memberships
          .filter((m) => m.active)
          .map(({ department_id, primary, backup, permissions }) => ({
            department_id,
            primary,
            backup,
            permissions,
          }));
        return person
          ? put(`/supervisors/${person.id}/permissions`, {
              departments: payload,
            })
          : post("/supervisors/invite", { ...values, departments: payload });
      }}
      onSuccess={onSaved}
    >
      <fieldset className="permission-grid">
        <legend>
          {w("Departments")} & {w("Permissions")}
        </legend>
        {departments.data
          ?.filter((d) => d.active)
          .map((dept) => {
            const membership = memberships.find(
              (m) => m.department_id === dept.id && m.active,
            );
            return (
              <div className="permission-row" key={dept.id}>
                <label className="check-field">
                  <input
                    type="checkbox"
                    checked={!!membership}
                    onChange={(event) =>
                      setMemberships((current) =>
                        event.target.checked
                          ? [
                              ...current.filter(
                                (m) => m.department_id !== dept.id,
                              ),
                              {
                                department_id: dept.id,
                                primary: false,
                                backup: false,
                                permissions: ["view"],
                                active: true,
                              } as (typeof memberships)[number],
                            ]
                          : current.filter((m) => m.department_id !== dept.id),
                      )
                    }
                  />
                  <strong>{dept.name}</strong>
                </label>
                {membership && (
                  <>
                    <div className="work-checks">
                      {(["primary", "backup"] as const).map((flag) => (
                        <label className="check-field" key={flag}>
                          <input
                            type="checkbox"
                            checked={membership[flag]}
                            onChange={(event) =>
                              update(dept.id, flag, event.target.checked)
                            }
                          />
                          {w(flag === "primary" ? "Primary" : "Backup")}
                        </label>
                      ))}
                    </div>
                    <div className="work-checks">
                      {permissions.map((permission) => (
                        <label className="check-field" key={permission}>
                          <input
                            type="checkbox"
                            checked={membership.permissions.includes(
                              permission,
                            )}
                            onChange={(event) =>
                              update(
                                dept.id,
                                "permissions",
                                event.target.checked
                                  ? [...membership.permissions, permission]
                                  : membership.permissions.filter(
                                      (p) => p !== permission,
                                    ),
                              )
                            }
                          />
                          {t(
                            {
                              view: "View",
                              manage: "Manage tasks",
                              review: "Review reports",
                              publish: "Publish handovers",
                              workforce: "Manage workers",
                              evidence: "Access evidence",
                            }[permission as "view"] || permission,
                            {
                              view: "देखें",
                              manage: "कार्य प्रबंधन",
                              review: "रिपोर्ट समीक्षा",
                              publish: "हैंडओवर प्रकाशन",
                              workforce: "कर्मचारी प्रबंधन",
                              evidence: "साक्ष्य देखें",
                            }[permission as "view"] || permission,
                          )}
                        </label>
                      ))}
                    </div>
                  </>
                )}
              </div>
            );
          })}
      </fieldset>
      <p className="field-hint">
        {t(
          "Primary supervisors need task management, report review and handover publication permissions. Only one primary supervisor per department.",
          "मुख्य पर्यवेक्षक को कार्य प्रबंधन, रिपोर्ट समीक्षा और हैंडओवर प्रकाशन की अनुमति चाहिए। प्रत्येक विभाग में एक मुख्य पर्यवेक्षक रखें।",
        )}
      </p>
    </FieldsForm>
  );
}

export function SupervisorsPage({ embedded = false }: { embedded?: boolean }) {
  const { supervisors, departments } = useCatalog();
  const w = useWords();
  const { t } = usePreferences();
  const [editor, setEditor] = useState<Person | "new" | "admin" | null>(null);
  const [stateTarget, setStateTarget] = useState<Person | null>(null);
  return (
    <>
      {!embedded && (
        <PageTitle
          title="Supervisors"
          description={t(
            "Invite people with individual accounts and explicit department permissions.",
            "हर व्यक्ति को निजी खाते और स्पष्ट विभागीय अनुमतियों के साथ आमंत्रित करें।",
          )}
        />
      )}
      <div className="work-actions section-actions">
        <button
          className="button button-primary"
          onClick={() => setEditor("new")}
        >
          {w("Invite supervisor")}
        </button>
        <button
          className="button button-outline"
          onClick={() => setEditor("admin")}
        >
          {w("Invite administrator")}
        </button>
      </div>
      <Panel>
        <When loading={supervisors.isLoading} error={supervisors.error}>
          {!supervisors.data?.length ? (
            <Empty />
          ) : (
            supervisors.data.map((person) => (
              <div className="work-list-row" key={person.id}>
                <div>
                  <Link
                    className="text-link"
                    to={`/workspace/supervisors/${person.id}`}
                  >
                    <strong>{person.name}</strong>
                  </Link>
                  <p>
                    {person.email} ·{" "}
                    {w(
                      person.role === "organization"
                        ? "Organization administrator"
                        : "Supervisor",
                    )}
                  </p>
                  <div className="work-tags">
                    <Status value={person.active ? "Active" : "Pending"} />
                    {person.departments?.map((m) => (
                      <span key={m.department_id}>
                        {
                          departments.data?.find(
                            (d) => d.id === m.department_id,
                          )?.name
                        }{" "}
                        ·{" "}
                        {w(
                          m.primary
                            ? "Primary"
                            : m.backup
                              ? "Backup"
                              : "Member",
                        )}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="work-actions">
                  {person.role === "supervisor" && (
                    <button
                      className="text-button"
                      onClick={() => setEditor(person)}
                    >
                      {w("Update permissions")}
                    </button>
                  )}
                  {!person.verified && (
                    <ActionButton
                      action={() => post(`/supervisors/${person.id}/resend`)}
                    >
                      {w("Resend invitation")}
                    </ActionButton>
                  )}
                  <button
                    className="text-button"
                    onClick={() => setStateTarget(person)}
                  >
                    {w(person.active ? "Deactivate" : "Reactivate")}
                  </button>
                </div>
              </div>
            ))
          )}
        </When>
      </Panel>
      {editor && (
        <Modal
          title={
            editor === "admin"
              ? "Invite administrator"
              : editor === "new"
                ? "Invite supervisor"
                : "Update permissions"
          }
          onClose={() => setEditor(null)}
        >
          {editor === "admin" ? (
            <FieldsForm
              fields={[
                { name: "name", label: "Full name", required: true },
                {
                  name: "email",
                  label: "Official email",
                  type: "email",
                  required: true,
                },
                { name: "phone", label: "Contact number" },
              ]}
              onSubmit={(values) =>
                post("/supervisors/invite", {
                  ...values,
                  role: "organization",
                  departments: [],
                })
              }
              onSuccess={() => setEditor(null)}
            />
          ) : (
            <PermissionForm
              person={typeof editor === "object" ? editor : undefined}
              onSaved={() => setEditor(null)}
            />
          )}
        </Modal>
      )}
      {stateTarget && (
        <Modal
          title={stateTarget.active ? "Deactivate" : "Reactivate"}
          onClose={() => setStateTarget(null)}
        >
          <p className="work-note">{stateTarget.name}</p>
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
              put(`/users/${stateTarget.id}/state`, {
                ...values,
                active: !stateTarget.active,
              })
            }
            onSuccess={() => setStateTarget(null)}
          />
        </Modal>
      )}
    </>
  );
}

type Policies = {
  privacy: Record<string, boolean | number>;
  security: { idle_minutes: number };
  operations: {
    deadline_reminder_minutes: number;
    handover_reminder_minutes: number;
    evidence_required_categories: string[];
  };
};
export function PoliciesPage({ section = "all" }: { section?: string }) {
  const { departments, teams, shifts, supervisors } = useCatalog();
  const { t } = usePreferences();
  const w = useWords();
  const policies = useQuery({
    queryKey: ["policies"],
    queryFn: () => api<Policies>("/policies"),
  });
  const mappings = useQuery({
    queryKey: ["responsibilities"],
    queryFn: () =>
      api<(Record<string, string> & { id: string })[]>("/responsibilities"),
  });
  const rules = useQuery({
    queryKey: ["escalation-rules"],
    queryFn: () =>
      api<
        {
          department_id: string;
          acknowledge_minutes: number;
          backup_minutes: number;
          escalation_recipient_id: string | null;
        }[]
      >("/escalation-rules"),
  });
  const takeovers = useQuery({
    queryKey: ["takeovers"],
    queryFn: () =>
      api<
        {
          id: string;
          department_id: string;
          reason: string;
          expires_at: string;
          user_id: string;
        }[]
      >("/takeovers"),
  });
  const [modal, setModal] = useState<
    "mapping" | "escalation" | "takeover" | null
  >(null);
  const show = (value: string) => section === "all" || section === value;
  const activeSupervisors = supervisors.data?.filter(
    (p) => p.role === "supervisor" && p.active,
  );
  return (
    <>
      {section === "all" && (
        <PageTitle
          title="Policies"
          description={t(
            "Privacy, responsibility and escalation rules are enforced on the server.",
            "गोपनीयता, जिम्मेदारी और एस्केलेशन के नियम सर्वर पर लागू हैं।",
          )}
        />
      )}
      {show("mapping") && (
        <Panel
          title="Responsibility mapping"
          action={
            <button
              className="button button-outline"
              onClick={() => setModal("mapping")}
            >
              {w("Create")}
            </button>
          }
        >
          {!mappings.data?.length ? (
            <Empty>
              {t(
                "Unmapped concerns go to the department’s primary supervisor.",
                "बिना मैपिंग वाले विषय विभाग के मुख्य पर्यवेक्षक को जाते हैं।",
              )}
            </Empty>
          ) : (
            mappings.data.map((mapping) => (
              <div className="work-list-row" key={mapping.id}>
                <div>
                  <strong>
                    {
                      departments.data?.find(
                        (d) => d.id === mapping.department_id,
                      )?.name
                    }
                  </strong>
                  <p>
                    {[mapping.machine, mapping.area, mapping.category]
                      .filter(Boolean)
                      .join(" · ") ||
                      t("All department concerns", "विभाग के सभी विषय")}
                  </p>
                  <small>
                    {
                      activeSupervisors?.find(
                        (s) => s.id === mapping.supervisor_id,
                      )?.name
                    }
                  </small>
                </div>
                <ActionButton
                  action={() => remove(`/responsibilities/${mapping.id}`)}
                >
                  {t("Remove mapping", "मैपिंग हटाएँ")}
                </ActionButton>
              </div>
            ))
          )}
        </Panel>
      )}
      {show("escalation") && (
        <Panel
          title="Alerts & escalation"
          action={
            <button
              className="button button-outline"
              onClick={() => setModal("escalation")}
            >
              {w("Save changes")}
            </button>
          }
        >
          <p className="work-note">
            {t(
              "Default: primary supervisor immediately; backup after 10 minutes without acknowledgement; organization administrators after another 10 minutes. Follow your workplace’s emergency procedure for immediate danger.",
              "डिफ़ॉल्ट: मुख्य पर्यवेक्षक को तुरंत; 10 मिनट तक पुष्टि न होने पर बैकअप; अगले 10 मिनट बाद प्रशासक। तत्काल खतरे में कार्यस्थल की आपातकालीन प्रक्रिया का पालन करें।",
            )}
          </p>
          {rules.data?.map((rule) => (
            <div className="work-list-row" key={rule.department_id}>
              <strong>
                {
                  departments.data?.find((d) => d.id === rule.department_id)
                    ?.name
                }
              </strong>
              <p>
                {rule.acknowledge_minutes} / {rule.backup_minutes}{" "}
                {t("minutes", "मिनट")}
              </p>
            </div>
          ))}
        </Panel>
      )}
      {show("privacy") && (
        <Panel title="Privacy & recording">
          <When loading={policies.isLoading} error={policies.error}>
            {policies.data && (
              <FieldsForm
                fields={[
                  {
                    name: "admin_report_access",
                    label: t(
                      "Allow audited administrator report access",
                      "प्रशासक को ऑडिट सहित रिपोर्ट पहुँच दें",
                    ),
                    type: "checkbox",
                    defaultValue: policies.data.privacy.admin_report_access,
                  },
                  {
                    name: "admin_recording_access",
                    label: t(
                      "Allow audited administrator evidence access",
                      "प्रशासक को ऑडिट सहित साक्ष्य पहुँच दें",
                    ),
                    type: "checkbox",
                    defaultValue: policies.data.privacy.admin_recording_access,
                  },
                  {
                    name: "photos_allowed",
                    label: t("Allow photo evidence", "फ़ोटो साक्ष्य की अनुमति"),
                    type: "checkbox",
                    defaultValue: policies.data.privacy.photos_allowed,
                  },
                  {
                    name: "videos_allowed",
                    label: t(
                      "Allow video evidence",
                      "वीडियो साक्ष्य की अनुमति",
                    ),
                    type: "checkbox",
                    defaultValue: policies.data.privacy.videos_allowed,
                  },
                  ...[
                    "audio_retention_days",
                    "transcript_retention_days",
                    "evidence_retention_days",
                  ].map((name, i) => ({
                    name,
                    label: t(
                      [
                        "Audio retention (days)",
                        "Transcript retention (days)",
                        "Evidence retention (days)",
                      ][i],
                      [
                        "ऑडियो रखने के दिन",
                        "ट्रांसक्रिप्ट रखने के दिन",
                        "साक्ष्य रखने के दिन",
                      ][i],
                    ),
                    type: "number" as const,
                    min: 1,
                    max: 3650,
                    defaultValue: policies.data!.privacy[name],
                  })),
                  {
                    name: "reason",
                    label: "Reason",
                    required: true,
                    wide: true,
                  },
                ]}
                onSubmit={(values) => {
                  const { reason, ...rest } = values;
                  return put("/policies/privacy", {
                    reason,
                    value: Object.fromEntries(
                      Object.entries(rest).map(([key, value]) => [
                        key,
                        key.endsWith("_days") ? Number(value) : value,
                      ]),
                    ),
                  });
                }}
              >
                <p className="field-hint">
                  {t(
                    "Recording always requires consent. Sensitive access requires a recorded purpose.",
                    "रिकॉर्डिंग के लिए सहमति हमेशा आवश्यक है। संवेदनशील जानकारी की पहुँच का उद्देश्य दर्ज करना ज़रूरी है।",
                  )}
                </p>
              </FieldsForm>
            )}
          </When>
        </Panel>
      )}
      {section === "all" && (
        <>
          <Panel title="Security & reminders">
            {policies.data && (
              <FieldsForm
                fields={[
                  {
                    name: "idle_minutes",
                    label: t(
                      "Inactivity timeout (minutes)",
                      "निष्क्रियता की समय सीमा (मिनट)",
                    ),
                    type: "number",
                    min: 1,
                    max: 3650,
                    defaultValue: policies.data.security.idle_minutes,
                  },
                  {
                    name: "deadline_reminder_minutes",
                    label: t(
                      "Deadline reminder (minutes before)",
                      "समय सीमा से पहले रिमाइंडर (मिनट)",
                    ),
                    type: "number",
                    min: 1,
                    max: 3650,
                    defaultValue:
                      policies.data.operations.deadline_reminder_minutes,
                  },
                  {
                    name: "handover_reminder_minutes",
                    label: t(
                      "Handover reminder (minutes)",
                      "हैंडओवर रिमाइंडर (मिनट)",
                    ),
                    type: "number",
                    min: 1,
                    max: 3650,
                    defaultValue:
                      policies.data.operations.handover_reminder_minutes,
                  },
                  {
                    name: "evidence_required_categories",
                    label: t(
                      "Categories requiring evidence",
                      "जिन श्रेणियों में साक्ष्य आवश्यक है",
                    ),
                    type: "multi",
                    options: [
                      "general",
                      "progress",
                      "safety",
                      "quality",
                      "equipment",
                      "maintenance",
                      "materials",
                    ].map((value) => ({ value, label: value })),
                    defaultValue:
                      policies.data.operations.evidence_required_categories,
                  },
                  { name: "reason", label: "Reason", required: true },
                ]}
                onSubmit={async (values) => {
                  await put("/policies/security", {
                    reason: values.reason,
                    value: { idle_minutes: Number(values.idle_minutes) },
                  });
                  return put("/policies/operations", {
                    reason: values.reason,
                    value: {
                      deadline_reminder_minutes: Number(
                        values.deadline_reminder_minutes,
                      ),
                      handover_reminder_minutes: Number(
                        values.handover_reminder_minutes,
                      ),
                      evidence_required_categories: list(
                        values.evidence_required_categories,
                      ),
                    },
                  });
                }}
              />
            )}
          </Panel>
          <Panel
            title="Temporary administrative takeover"
            action={
              <button
                className="button button-outline"
                onClick={() => setModal("takeover")}
              >
                {t("Start takeover", "अस्थायी जिम्मेदारी लें")}
              </button>
            }
          >
            <p className="work-note">
              {t(
                "A takeover grants operational permissions for one department for up to 24 hours. Every action remains attributed to you.",
                "अस्थायी जिम्मेदारी एक विभाग की संचालन अनुमति अधिकतम 24 घंटे देती है। हर कार्रवाई आपके नाम से दर्ज होगी।",
              )}
            </p>
            {takeovers.data?.map((takeover) => (
              <div className="work-list-row" key={takeover.id}>
                <div>
                  <strong>
                    {
                      departments.data?.find(
                        (d) => d.id === takeover.department_id,
                      )?.name
                    }
                  </strong>
                  <p>{takeover.reason}</p>
                  <small>{formatDate(takeover.expires_at)}</small>
                </div>
                <ActionButton
                  action={() => remove(`/takeovers/${takeover.id}`)}
                >
                  {t("End takeover", "जिम्मेदारी समाप्त करें")}
                </ActionButton>
              </div>
            ))}
          </Panel>
        </>
      )}
      {modal && (
        <Modal
          title={
            modal === "mapping"
              ? "Responsibility mapping"
              : modal === "escalation"
                ? "Alerts & escalation"
                : "Temporary administrative takeover"
          }
          onClose={() => setModal(null)}
        >
          <FieldsForm
            fields={[
              {
                name: "department_id",
                label: "Department",
                type: "select",
                required: true,
                options: options(departments.data?.filter((d) => d.active)),
              },
              ...(modal === "mapping"
                ? ([
                    {
                      name: "supervisor_id",
                      label: "Primary",
                      type: "select",
                      required: true,
                      options: options(activeSupervisors),
                    },
                    {
                      name: "backup_id",
                      label: "Backup",
                      type: "select",
                      options: options(activeSupervisors),
                    },
                    {
                      name: "team_id",
                      label: "Team",
                      type: "select",
                      options: options(teams.data?.filter((t) => t.active)),
                    },
                    {
                      name: "shift_id",
                      label: "Shift",
                      type: "select",
                      options: options(shifts.data?.filter((s) => s.active)),
                    },
                    { name: "machine", label: "Machine / equipment" },
                    { name: "area", label: "Work area" },
                    { name: "category", label: "Category" },
                  ] as FieldSpec[])
                : modal === "escalation"
                  ? ([
                      {
                        name: "acknowledge_minutes",
                        label: t(
                          "Primary response window (minutes)",
                          "मुख्य पर्यवेक्षक की समय सीमा (मिनट)",
                        ),
                        type: "number",
                        min: 1,
                        max: 240,
                        defaultValue: 10,
                      },
                      {
                        name: "backup_minutes",
                        label: t(
                          "Backup response window (minutes)",
                          "बैकअप की समय सीमा (मिनट)",
                        ),
                        type: "number",
                        min: 1,
                        max: 240,
                        defaultValue: 10,
                      },
                      {
                        name: "channels",
                        label: t(
                          "Critical alert channels",
                          "गंभीर अलर्ट के माध्यम",
                        ),
                        type: "multi",
                        defaultValue: ["in_app"],
                        options: [
                          {
                            value: "in_app",
                            label: t(
                              "In-app (always enabled)",
                              "ऐप में (हमेशा चालू)",
                            ),
                          },
                          {
                            value: "email",
                            label: t(
                              "Email to responsible supervisors and administrators",
                              "जिम्मेदार पर्यवेक्षकों और प्रशासकों को ईमेल",
                            ),
                          },
                        ],
                      },
                      {
                        name: "escalation_recipient_id",
                        label: "Organization administrator",
                        type: "select",
                        options: options(
                          supervisors.data?.filter(
                            (s) => s.role === "organization" && s.active,
                          ),
                        ),
                      },
                    ] as FieldSpec[])
                  : ([
                      {
                        name: "reason",
                        label: "Reason",
                        type: "textarea",
                        required: true,
                      },
                      {
                        name: "hours",
                        label: "Hours",
                        type: "number",
                        min: 1,
                        max: 24,
                        defaultValue: 8,
                      },
                    ] as FieldSpec[])),
            ]}
            onSubmit={(values) =>
              modal === "mapping"
                ? post("/responsibilities", {
                    ...values,
                    backup_id: nullable(values.backup_id),
                    team_id: nullable(values.team_id),
                    shift_id: nullable(values.shift_id),
                  })
                : modal === "escalation"
                  ? put("/escalation-rules", {
                      ...values,
                      acknowledge_minutes: Number(values.acknowledge_minutes),
                      backup_minutes: Number(values.backup_minutes),
                      escalation_recipient_id: nullable(
                        values.escalation_recipient_id,
                      ),
                      channels: Array.from(
                        new Set(["in_app", ...list(values.channels)]),
                      ),
                      active: true,
                    })
                  : post("/takeovers", {
                      ...values,
                      hours: Number(values.hours),
                    })
            }
            onSuccess={() => setModal(null)}
          />
        </Modal>
      )}
    </>
  );
}

type OnboardingStatus = {
  current_step: number;
  can_activate: boolean;
  active: boolean;
  steps: { number: number; name: string; required: boolean; status: string }[];
};
export function OnboardingPage() {
  const { t } = usePreferences();
  const w = useWords();
  const state = useQuery({
    queryKey: ["onboarding"],
    queryFn: () => api<OnboardingStatus>("/organization/onboarding"),
  });
  const [selected, setSelected] = useState<number | null>(null);
  const step = selected || state.data?.current_step || 1;
  return (
    <>
      <PageTitle
        title="Onboarding"
        description={t(
          "Nine steps to a clear handover. The first five are required; progress is saved in your workspace.",
          "स्पष्ट हैंडओवर के लिए नौ चरण। पहले पाँच आवश्यक हैं; प्रगति कार्यस्थल में सहेजी जाती है।",
        )}
      >
        <Link className="button button-outline" to="/workspace">
          {w("Save & exit")}
        </Link>
      </PageTitle>
      <When loading={state.isLoading} error={state.error}>
        {state.data && (
          <>
            <div className="onboarding-steps">
              {state.data.steps.map((item) => (
                <button
                  key={item.number}
                  className={step === item.number ? "step-current" : ""}
                  onClick={() => setSelected(item.number)}
                >
                  <span>
                    {item.status === "completed" ? (
                      <CheckCircle2 size={17} />
                    ) : (
                      String(item.number).padStart(2, "0")
                    )}
                  </span>
                  <strong>
                    {t(
                      item.name,
                      [
                        "संगठन प्रोफ़ाइल",
                        "विभाग",
                        "टीम और उत्पादन लाइन",
                        "शिफ्ट संरचना",
                        "सक्रिय मुख्य पर्यवेक्षक",
                        "जिम्मेदारी मैपिंग",
                        "एस्केलेशन नियम",
                        "गोपनीयता नीति",
                        "अंतिम समीक्षा",
                      ][item.number - 1],
                    )}
                  </strong>
                  <Status value={item.status} />
                </button>
              ))}
            </div>
            <section className="onboarding-content">
              {step === 1 ? (
                <Panel title="Organization profile">
                  <OrganizationProfile />
                </Panel>
              ) : step === 2 || step === 3 ? (
                <DepartmentsPage embedded />
              ) : step === 4 ? (
                <ShiftsPage embedded />
              ) : step === 5 ? (
                <>
                  <SupervisorsPage embedded />
                  <p className="work-note">
                    {t(
                      "A supervisor must accept their invitation and choose a password before activation. Pending invitations do not satisfy this requirement.",
                      "सक्रिय करने से पहले पर्यवेक्षक को आमंत्रण स्वीकार करके पासवर्ड बनाना होगा। केवल लंबित आमंत्रण पर्याप्त नहीं है।",
                    )}
                  </p>
                  <button
                    className="button button-outline"
                    onClick={() => void state.refetch()}
                  >
                    {w("Refresh status")}
                  </button>
                </>
              ) : step >= 6 && step <= 8 ? (
                <PoliciesPage
                  section={["mapping", "escalation", "privacy"][step - 6]}
                />
              ) : (
                <Panel title="Final review">
                  <div className="work-summary">
                    {state.data.steps.map((item) => (
                      <div className="work-list-row" key={item.number}>
                        <button
                          className="text-button"
                          onClick={() => setSelected(item.number)}
                        >
                          {item.number}. {item.name}
                        </button>
                        <Status value={item.status} />
                      </div>
                    ))}
                  </div>
                </Panel>
              )}
            </section>
            <div className="work-actions onboarding-actions">
              {step < 9 && (
                <ActionButton
                  className="button button-primary"
                  action={async () => {
                    await post("/organization/onboarding", { step });
                    setSelected(step + 1);
                  }}
                >
                  {w("Save & continue")}
                </ActionButton>
              )}
              {step > 5 && (
                <ActionButton
                  action={async () => {
                    await post("/organization/onboarding", {
                      step,
                      skip: true,
                    });
                    setSelected(Math.min(9, step + 1));
                  }}
                >
                  {w("Skip optional step")}
                </ActionButton>
              )}
              {state.data.can_activate && !state.data.active && (
                <ActionButton
                  className="button button-primary"
                  action={() => post("/organization/activate")}
                >
                  {w("Activate organization")}
                </ActionButton>
              )}
              {state.data.active && (
                <Link to="/workspace" className="button button-primary">
                  {t("Open workspace", "कार्यस्थल खोलें")}
                </Link>
              )}
            </div>
          </>
        )}
      </When>
    </>
  );
}
