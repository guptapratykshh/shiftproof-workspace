import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { TriangleAlert } from "lucide-react";
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
  options,
  useWords,
} from "../../components/workspace/UI";
import { api, post } from "../../lib/api";
import { useSession } from "../../lib/session";
import { usePreferences } from "../../lib/preferences";
import type { AlertRecord, Paged, Task } from "../../lib/types";
import { TaskForm } from "./Tasks";

export function AlertsPage() {
  const { id } = useParams();
  const session = useSession((state) => state.session)!;
  const management = session.user.role !== "worker";
  const { departments, supervisors } = useCatalog();
  const { t } = usePreferences();
  const w = useWords();
  const [modal, setModal] = useState<string | null>(null);
  const data = useQuery<AlertRecord | AlertRecord[]>({
    queryKey: ["alerts", id],
    queryFn: () =>
      id ? api<AlertRecord>(`/alerts/${id}`) : api<AlertRecord[]>("/alerts"),
  });
  const tasks = useQuery({
    queryKey: ["tasks", "alert", id],
    queryFn: () => api<Paged<Task>>("/tasks?limit=200"),
    enabled: !!id && management,
  });
  const item = id ? (data.data as AlertRecord | undefined) : undefined;
  return (
    <>
      <PageTitle
        title="Alerts"
        description={t(
          "Acknowledge quickly, inspect the source, and verify the resolution separately.",
          "जल्द प्राप्ति की पुष्टि करें, स्रोत जाँचें और समाधान अलग से सत्यापित करें।",
        )}
      />
      <div className="emergency-note">
        <TriangleAlert size={20} />
        <p>
          {t(
            "For immediate danger, follow your workplace’s emergency procedure. ShiftProof supports coordination and does not replace emergency response.",
            "तत्काल खतरे में कार्यस्थल की आपातकालीन प्रक्रिया अपनाएँ। ShiftProof समन्वय में मदद करता है, आपातकालीन सहायता का विकल्प नहीं है।",
          )}
        </p>
      </div>
      <When loading={data.isLoading} error={data.error}>
        {item ? (
          <>
            <Panel>
              <div className="work-tags section-actions">
                <Status value={item.status} />
                <Status value={item.severity} />
                <span>
                  {
                    departments.data?.find((d) => d.id === item.department_id)
                      ?.name
                  }
                </span>
              </div>
              <h2>{item.title}</h2>
              <dl className="work-definition">
                <div>
                  <dt>{t("Responsible person", "जिम्मेदार व्यक्ति")}</dt>
                  <dd>
                    {supervisors.data?.find(
                      (person) => person.id === item.assigned_to,
                    )?.name ||
                      (item.assigned_to === session.user.id
                        ? session.user.name
                        : t("Designated responder", "निर्धारित उत्तरदाता"))}
                  </dd>
                </div>
                <div>
                  <dt>{t("Escalation level", "एस्केलेशन स्तर")}</dt>
                  <dd>{item.escalation_level}</dd>
                </div>
                <div>
                  <dt>{t("Acknowledged at", "प्राप्ति की पुष्टि का समय")}</dt>
                  <dd>
                    {formatDate(
                      item.acknowledged_at,
                      session.organization.timezone,
                    )}
                  </dd>
                </div>
              </dl>
              {item.resolution && (
                <p className="instruction-box">{item.resolution}</p>
              )}
              <div className="work-actions">
                {item.report_id && (
                  <Link
                    className="button button-outline"
                    to={`/workspace/reports/${item.report_id}`}
                  >
                    {w("View source")}
                  </Link>
                )}
                {item.task_id && (
                  <Link
                    className="button button-outline"
                    to={`/workspace/tasks/${item.task_id}`}
                  >
                    {w("Corrective task")}
                  </Link>
                )}
                {management && (
                  <>
                    {item.status === "new" && (
                      <ActionButton
                        className="button button-primary"
                        action={() =>
                          post(`/alerts/${id}/actions`, {
                            action: "acknowledge",
                            version: item.version,
                          })
                        }
                      >
                        {w("Acknowledge")}
                      </ActionButton>
                    )}
                    {["acknowledged", "in_progress"].includes(item.status) && (
                      <>
                        <button
                          className="button button-outline"
                          onClick={() => setModal("task")}
                        >
                          {w("Create task")}
                        </button>
                        <button
                          className="button button-outline"
                          onClick={() => setModal("assign")}
                        >
                          {t("Link corrective task", "सुधारात्मक कार्य जोड़ें")}
                        </button>
                        <button
                          className="button button-primary"
                          onClick={() => setModal("verify")}
                        >
                          {t("Verify resolution", "समाधान सत्यापित करें")}
                        </button>
                      </>
                    )}
                    {item.status === "verified" && (
                      <ActionButton
                        className="button button-primary"
                        action={() =>
                          post(`/alerts/${id}/actions`, {
                            action: "resolve",
                            version: item.version,
                          })
                        }
                      >
                        {w("Resolve issue")}
                      </ActionButton>
                    )}
                  </>
                )}
              </div>
            </Panel>
            <Panel title="History">
              <ol className="work-timeline">
                {item.history?.map((event) => (
                  <li key={event.id}>
                    <span className="timeline-dot" />
                    <div>
                      <strong>{w(event.action)}</strong>
                      <p>{String(event.detail.note || "")}</p>
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
            {modal && (
              <Modal
                title={
                  modal === "task"
                    ? "Create task"
                    : modal === "assign"
                      ? "Corrective task"
                      : "Resolution"
                }
                onClose={() => setModal(null)}
              >
                {modal === "task" ? (
                  <TaskForm
                    critical
                    departmentId={item.department_id}
                    sourceReportId={item.report_id || undefined}
                    onSaved={() => setModal("assign")}
                  />
                ) : (
                  <FieldsForm
                    fields={
                      modal === "assign"
                        ? [
                            {
                              name: "task_id",
                              label: "Corrective task",
                              type: "select",
                              required: true,
                              options: options(
                                tasks.data?.items.filter(
                                  (task) =>
                                    task.critical &&
                                    task.department_id === item.department_id &&
                                    (!item.report_id ||
                                      task.source_report_id === item.report_id),
                                ),
                              ),
                            },
                          ]
                        : [
                            {
                              name: "note",
                              label: "Resolution",
                              type: "textarea",
                              required: true,
                            },
                          ]
                    }
                    onSubmit={(values) =>
                      post(`/alerts/${id}/actions`, {
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
        ) : (
          <Panel>
            {!(data.data as AlertRecord[] | undefined)?.length ? (
              <Empty />
            ) : (
              (data.data as AlertRecord[]).map((alert) => (
                <Link
                  className="work-list-row"
                  to={`/workspace/alerts/${alert.id}`}
                  key={alert.id}
                >
                  <span className="list-icon">
                    <TriangleAlert size={22} />
                  </span>
                  <div className="row-grow">
                    <strong>{alert.title}</strong>
                    <p>
                      {
                        departments.data?.find(
                          (d) => d.id === alert.department_id,
                        )?.name
                      }{" "}
                      ·{" "}
                      {formatDate(
                        alert.created_at,
                        session.organization.timezone,
                      )}
                    </p>
                    {alert.escalation_level > 0 && (
                      <p className="work-warning">
                        {t("Escalated", "आगे भेजा गया")} ·{" "}
                        {alert.escalation_level}
                      </p>
                    )}
                  </div>
                  <Status value={alert.status} />
                </Link>
              ))
            )}
          </Panel>
        )}
      </When>
    </>
  );
}
